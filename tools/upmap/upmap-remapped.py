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

try:
  OSDS = json.loads(subprocess.getoutput('ceph osd ls -f json'))
  DF = json.loads(subprocess.getoutput('ceph osd df -f json | jq .nodes'))
except ValueError:
  eprint('Error loading OSD IDs')
  sys.exit(1)

def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

def crush_weight(id):
  for o in DF:
    if o['id'] == id:
      return o['crush_weight'] * o['reweight']
  return 0

def gen_upmap(up, acting):
  assert(len(up) == len(acting))
  pairs = []
  for p in zip(up, acting):
    if p[0] != p[1] and p[0] in OSDS and crush_weight(p[1]) > 0:
      pairs.append(p)
  return pairs

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
  remapped_json = subprocess.getoutput('ceph pg ls remapped -f json')
  remapped = json.loads(remapped_json)
except ValueError:
  eprint('Error loading remapped pgs')
  sys.exit(1)

# nautilus compat
try:
  _remapped = remapped['pg_stats']
  remapped = _remapped
except KeyError:
  print("There are no remapped PGs")
  sys.exit(0)

# discover existing upmaps
osd_dump_json = subprocess.getoutput('ceph osd dump -f json')
osd_dump = json.loads(osd_dump_json)
upmaps = osd_dump['pg_upmap_items']

# discover pools replicated or erasure
pool_type = {}
try:
  for line in subprocess.getoutput('ceph osd pool ls detail').split('\n'):
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
print('while ceph status | grep -q "peering\|activating"; do sleep 2; done')
num = 0
for pg in remapped:
  if num == 50:
    print('wait; sleep 4; while ceph status | grep -q "peering\|activating"; do sleep 2; done')
    num = 0

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
      pairs = gen_upmap(up, acting)
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

print('wait; sleep 4; while ceph status | grep -q "peering\|activating"; do sleep 2; done')
