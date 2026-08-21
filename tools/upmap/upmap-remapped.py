#!/usr/bin/env python3
#
# DISCLAIMER: THIS SCRIPT COMES WITH NO WARRANTY OR GUARANTEE
# OF ANY KIND.
#
# DISCLAIMER 2: THIS TOOL USES A CEPH FEATURE MARKED "(developers only)"
# YOU SHOULD NOT RUN THIS UNLESS YOU KNOW EXACTLY HOW THOSE
# FUNCTIONALITIES WORK.
#
# upmap-remapped.py
#
# Usage (print only): ./upmap-remapped.py
# Usage (production): ./upmap-remapped.py | sh
#
# Optional to ignore PGs that are backfilling and not backfill+wait:
# Usage: ./upmap-remapped.py --ignore-backfilling
#
# This tool will use ceph's pg-upmap-items functionality to
# quickly modify all PGs which are currently remapped to become
# active+clean. I use it in combination with the ceph-mgr upmap
# balancer and the norebalance state for these use-cases:
#
# - Change crush rules or tunables.
# - Adding capacity (add new host, rack, ...).
#
# In general, the correct procedure for using this script is:
#
# 1. Backup your osdmaps, crush maps, ...
# 2. Set the norebalance flag.
# 3. Make your change (tunables, add osds, etc...)
# 4. Run this script a few times. (Remember to | sh)
# 5. Cluster should now be 100% active+clean.
# 6. Unset the norebalance flag.
# 7. The ceph-mgr balancer in upmap mode should now gradually
#    remove the upmap-items entries which were created by this
#    tool.
#
# Hacked by: Dan van der Ster <daniel.vanderster@cern.ch>


import json, subprocess, sys

def get_command_output(command):
  result = subprocess.run(command, capture_output=True, universal_newlines=True, check=True, shell=True)
  return result.stdout

try:
  import rados
  cluster = rados.Rados(conffile='/etc/ceph/ceph.conf')
  cluster.connect()
except:
  use_shell = True
else:
  use_shell = False

def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

try:
  if use_shell:
    OSDS = json.loads(get_command_output('ceph osd ls -f json | jq -r .'))
    DF = json.loads(get_command_output('ceph osd df -f json | jq -r .nodes'))
  else:
    cmd = {"prefix": "osd ls", "format": "json"}
    ret, output, errs = cluster.mon_command(json.dumps(cmd), b'', timeout=5)
    output = output.decode('utf-8').strip()
    OSDS = json.loads(output)
    cmd = {"prefix": "osd df", "format": "json"}
    ret, output, errs = cluster.mon_command(json.dumps(cmd), b'', timeout=5)
    output = output.decode('utf-8').strip()
    DF = json.loads(output)['nodes']
except ValueError:
  eprint('Error loading OSD IDs')
  sys.exit(1)

ignore_backfilling = False
for arg in sys.argv[1:]:
  if arg == "--ignore-backfilling":
    eprint ("All actively backfilling PGs will be ignored.")
    ignore_backfilling = True

def crush_weight(id):
  for o in DF:
    if o['id'] == id:
      return o['crush_weight'] * o['reweight']
  return 0

def gen_upmap(up, acting, replicated=False):
  assert(len(up) == len(acting))

  # On replicated pools only the set of osds matters, so vacate the osds which do
  # not belong in the pg and fill it with the ones which are missing from it.
  # This never maps onto an osd which is already in the up set, which the mon
  # would ignore.
  # e.g. ceph osd pg-upmap-items 4.5fd 603 383 499 804
  if replicated:
    sources = [u for u in up if u not in acting and u in OSDS]
    dests = [a for a in acting if a not in up and crush_weight(a) > 0]
    return list(zip(sources, dests))

  # On erasure-coded pools every position in the up set matters, so the mappings
  # have to be positional.  Only keep the ones we are allowed to make.
  mappings = [(u, a) for u, a in zip(up, acting) if u != a and u in OSDS and crush_weight(a) > 0]

  # Dropping a mapping above leaves its osd in the up set, and mapping onto an
  # osd which is staying in the up set asks for the same osd twice, which the mon
  # ignores.  Drop those mappings too, repeating until nothing changes.
  while True:
    staying = set(up) - set(u for u, a in mappings)
    keep = [(u, a) for u, a in mappings if a not in staying]
    if len(keep) == len(mappings):
      break
    mappings = keep

  # Order the mappings on erasure-coded pools so that data is moved off an osd
  # before it is moved on to it.
  # e.g. ceph osd pg-upmap-items 15.c9 714 803 929 714
  # Each osd is used at most once as a source and once as a destination, so the
  # mappings form chains and cycles.  Emit each chain in order.  A cycle, such as
  # (314, 272) & (272, 314) or 1 -> 2 -> 3 -> 1, has no valid order, so leave
  # those mappings out and let the pg stay remapped.
  by_source = dict((u, (u, a)) for u, a in mappings)
  ordered = []
  placed = set()
  for m in mappings:
    if m in placed:
      continue
    # walk back over the mappings which have to be done before this one
    chain = []
    n = m
    while n is not None and n not in placed and n not in chain:
      chain.append(n)
      n = by_source.get(n[1])
    placed.update(chain)
    if n in chain:
      continue
    chain.reverse()
    ordered.extend(chain)

  return ordered

def upmap_pg_items(pgid, mapping):
  if len(mapping):
    print('ceph osd pg-upmap-items %s ' % pgid, end='')
    for pair in mapping:
      print('%s %s ' % pair, end='')
    print('&')

def rm_upmap_pg_items(pgid):
  print('ceph osd rm-pg-upmap-items %s &' % pgid)


# start here

# discover remapped pgs
try:
  if use_shell:
    remapped_json = get_command_output('ceph pg ls remapped -f json | jq -r .')
  else:
    cmd = {"prefix": "pg ls", "states": ["remapped"], "format": "json"}
    ret, output, err = cluster.mon_command(json.dumps(cmd), b'', timeout=5)
    remapped_json = output.decode('utf-8').strip()
  try:
    remapped = json.loads(remapped_json)['pg_stats']
  except KeyError:
    eprint("There are no remapped PGs")
    sys.exit(0)
except ValueError:
  eprint('Error loading remapped pgs')
  sys.exit(1)

# discover existing upmaps
try:
  if use_shell:
    osd_dump_json = get_command_output('ceph osd dump -f json | jq -r .')
  else:
    cmd = {"prefix": "osd dump", "format": "json"}
    ret, output, errs = cluster.mon_command(json.dumps(cmd), b'', timeout=5)
    osd_dump_json = output.decode('utf-8').strip()
  upmaps = json.loads(osd_dump_json)['pg_upmap_items']
except ValueError:
  eprint('Error loading existing upmaps')
  sys.exit(1)

# discover pools replicated or erasure
pool_type = {}
try:
  if use_shell:
    osd_pool_ls_detail = get_command_output('ceph osd pool ls detail')
  else:
    cmd = {"prefix": "osd pool ls", "detail": "detail", "format": "plain"}
    ret, output, errs = cluster.mon_command(json.dumps(cmd), b'', timeout=5)
    osd_pool_ls_detail = output.decode('utf-8').strip()
  for line in osd_pool_ls_detail.split('\n'):
    if 'pool' in line:
      x = line.split(' ')
      pool_type[x[1]] = x[3]
except:
  eprint('Error parsing pool types')
  sys.exit(1)

# discover if each pg is already upmapped
has_upmap = {}
for pg in upmaps:
  pgid = str(pg['pgid'])
  has_upmap[pgid] = True

# handle each remapped pg
print(r'while ceph status | grep -q "peering\|activating\|laggy"; do sleep 2; done')
num = 0
for pg in remapped:
  if num == 50:
    print(r'wait; sleep 4; while ceph status | grep -q "peering\|activating\|laggy"; do sleep 2; done')
    num = 0

  if ignore_backfilling:
    if "backfilling" in pg['state']:
      continue

  pgid = pg['pgid']

  try:
    if has_upmap[pgid]:
      rm_upmap_pg_items(pgid)
      num += 1
      continue
  except KeyError:
    pass

  up = pg['up']
  acting = pg['acting']
  pool = pgid.split('.')[0]
  if pool_type[pool] == 'replicated':
    try:
      pairs = gen_upmap(up, acting, replicated=True)
    except:
      continue
  elif pool_type[pool] == 'erasure':
    try:
      pairs = gen_upmap(up, acting)
    except:
      continue
  else:
    eprint('Unknown pool type for %s' % pool)
    sys.exit(1)
  upmap_pg_items(pgid, pairs)
  num += 1

print(r'wait; sleep 4; while ceph status | grep -q "peering\|activating\|laggy"; do sleep 2; done')

if not use_shell:
  cluster.shutdown()
