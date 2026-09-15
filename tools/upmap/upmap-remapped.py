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


import argparse, atexit, json, subprocess, sys

# How long to wait for a mon command.  'pg ls' and 'osd dump' can take a while
# on a large cluster with many remapped pgs.
MON_TIMEOUT = 300

# The cluster state every function below works from.  main() fills it in; the
# tests set it directly.
OSDS = set()      # the osds which exist, from 'osd ls'
WEIGHT = {}       # osd id -> the weight it effectively has, from 'osd df'
UP = None         # the osds which are up, from 'osd dump' (None: do not check)

# the crush tree and the rules, from 'osd crush dump'
PARENT = {}       # bucket or osd id -> the id of the bucket holding it
BUCKET_TYPE = {}  # bucket id -> its crush type id
CHILDREN = {}     # bucket id -> the ids it holds
RULE_DOMAIN = {}  # crush rule id -> the crush type id it separates pgs over
POOL_RULE = {}    # pool id (as a string) -> the crush rule it uses
_domain_of = {}   # (osd id, crush type id) -> the bucket of that type above it
_domain_osds = {} # crush type id -> ([bucket ids], {bucket id: [usable osds]})
cluster = None    # the librados connection, or None when using the shell
use_shell = True

def get_command_output(command):
  result = subprocess.run(command, capture_output=True, universal_newlines=True, check=True, shell=True)
  return result.stdout

def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

def parse_args():
  parser = argparse.ArgumentParser(
    description='Print the ceph commands which make every remapped pg '
                'active+clean again.  Pipe the output into sh to run them.')
  parser.add_argument('--ignore-backfilling', action='store_true',
                      help='leave the pgs which are already backfilling alone, '
                           'instead of interrupting them')
  return parser.parse_args()

def connect():
  """Talk to the cluster through librados when it is available, and fall back to
  running the ceph cli in a shell when it is not."""
  global cluster, use_shell
  try:
    import rados
    cluster = rados.Rados(conffile='/etc/ceph/ceph.conf')
    cluster.connect()
  except Exception:
    use_shell = True
  else:
    use_shell = False
    # every exit from here on should close the connection, not just the last one
    atexit.register(cluster.shutdown)

def get_cluster_output(shell_command, mon_command):
  """Run a command through librados if it is available, else through the shell,
  and return its output.  Exits if the command fails."""
  try:
    if use_shell:
      return get_command_output(shell_command)
    ret, output, errs = cluster.mon_command(json.dumps(mon_command), b'',
                                            timeout=MON_TIMEOUT)
  except Exception as e:
    eprint('Error running "%s": %s' % (shell_command, e))
    sys.exit(1)
  if ret != 0:
    eprint('Error running "%s": %s'
           % (shell_command, errs.strip() or 'returned %d' % ret))
    sys.exit(1)
  return output.decode('utf-8').strip()

def load_osds():
  """Read the osds which exist and the weight each of them effectively has."""
  global OSDS, WEIGHT
  try:
    OSDS = set(json.loads(get_cluster_output('ceph osd ls -f json',
                                             {"prefix": "osd ls", "format": "json"})))
    DF = json.loads(get_cluster_output('ceph osd df -f json',
                                       {"prefix": "osd df", "format": "json"}))['nodes']
  except ValueError:
    eprint('Error loading OSD IDs')
    sys.exit(1)
  # gen_upmap() asks about this for every shard of every remapped pg
  WEIGHT = dict((o['id'], o['crush_weight'] * o['reweight']) for o in DF)

def crush_weight(id):
  return WEIGHT.get(id, 0)

def is_up(id):
  return UP is None or id in UP

def usable(id):
  """Whether a pg may be mapped onto this osd.  An osd which is out has nowhere
  to put the data, and one which is down would leave the pg degraded until it
  comes back, which is worse than leaving the pg remapped."""
  return crush_weight(id) > 0 and is_up(id)

def build_topology(crush, osd_dump):
  """Take the crush tree, the failure domain of every rule and the rule every
  pool uses out of 'osd crush dump' and 'osd dump'."""
  type_id = dict((t['name'], t['type_id']) for t in crush.get('types', []))
  for bucket in crush.get('buckets', []):
    if '~' in bucket['name']:
      continue                    # a shadow bucket of the per-device-class tree
    BUCKET_TYPE[bucket['id']] = bucket['type_id']
    CHILDREN[bucket['id']] = [item['id'] for item in bucket.get('items', [])]
    for item in bucket.get('items', []):
      PARENT[item['id']] = bucket['id']
  for rule in crush.get('rules', []):
    # Only a rule which separates the pg over one type of bucket - the usual
    # 'chooseleaf firstn 0 type host' - is modelled here.  A rule which chooses
    # several buckets and then several osds inside each of them constrains the
    # pg in a way this cannot express, so leave its domain unknown.
    steps = [step.get('type') for step in rule.get('steps', [])
             if str(step.get('op', '')).startswith('choose')]
    RULE_DOMAIN[rule['rule_id']] = type_id.get(steps[0]) if len(steps) == 1 else None
  for pool in osd_dump.get('pools', []):
    POOL_RULE[str(pool['pool'])] = pool['crush_rule']

def domain_of(osd, domain_type):
  """The bucket of the failure domain type which holds this osd, or None."""
  key = (osd, domain_type)
  if key not in _domain_of:
    bucket = PARENT.get(osd)
    while bucket is not None and BUCKET_TYPE.get(bucket) != domain_type:
      bucket = PARENT.get(bucket)
    _domain_of[key] = bucket
  return _domain_of[key]

def osds_under(bucket, found):
  for child in CHILDREN.get(bucket, []):
    if child >= 0:
      found.append(child)
    else:
      osds_under(child, found)
  return found

def domains(domain_type):
  """Every bucket of the failure domain type, and the osds a pg can be mapped
  onto inside each of them."""
  if domain_type not in _domain_osds:
    buckets = sorted(b for b, t in BUCKET_TYPE.items() if t == domain_type)
    _domain_osds[domain_type] = (
      buckets,
      dict((b, sorted(o for o in osds_under(b, []) if usable(o))) for b in buckets))
  return _domain_osds[domain_type]

def gen_upmap(up, acting, replicated=False):
  # a pg which is degraded as well as remapped can report an acting set of a
  # different length, and there is nothing useful to do with those
  if len(up) != len(acting):
    return []

  # On replicated pools only the set of osds matters, so vacate the osds which do
  # not belong in the pg and fill it with the ones which are missing from it.
  # This never maps onto an osd which is already in the up set, which the mon
  # would ignore.
  # e.g. ceph osd pg-upmap-items 4.5fd 603 383 499 804
  if replicated:
    sources = [u for u in up if u not in acting and u in OSDS]
    dests = [a for a in acting if a not in up and usable(a)]
    return list(zip(sources, dests))

  # On erasure-coded pools every position in the up set matters, so the mappings
  # have to be positional.  Only keep the ones we are allowed to make.
  mappings = [(u, a) for u, a in zip(up, acting) if u != a and u in OSDS and usable(a)]

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

def reverse_upmap(up, mappings):
  """Return the up set crush would have given this pg without its pg-upmap-items.

  'pg ls' reports the up set the mon has already applied the pg's upmap items
  to, while pg-upmap-items is expressed against the mapping crush produces.  The
  mon applied each item by putting 'to' where 'from' was, so undo them in
  reverse order."""
  raw = list(up)
  for mapping in reversed(mappings):
    for i, osd in enumerate(raw):
      if osd == mapping['to']:
        raw[i] = mapping['from']
        break
  return raw

def upmap_pg_items(pgid, mapping):
  if len(mapping):
    print('ceph osd pg-upmap-items %s ' % pgid, end='')
    for pair in mapping:
      print('%s %s ' % pair, end='')
    print('&')

def rm_upmap_pg_items(pgid):
  print('ceph osd rm-pg-upmap-items %s &' % pgid)

def main():
  options = parse_args()
  if options.ignore_backfilling:
    eprint('All actively backfilling PGs will be ignored.')

  connect()
  load_osds()

  # discover remapped pgs
  try:
    remapped_json = get_cluster_output('ceph pg ls remapped -f json',
                                       {"prefix": "pg ls", "states": ["remapped"], "format": "json"})
    try:
      remapped = json.loads(remapped_json)['pg_stats']
    except KeyError:
      eprint("There are no remapped PGs")
      sys.exit(0)
  except ValueError:
    eprint('Error loading remapped pgs')
    sys.exit(1)

  # discover existing upmaps and which osds are up
  global UP
  try:
    osd_dump = json.loads(get_cluster_output('ceph osd dump -f json',
                                             {"prefix": "osd dump", "format": "json"}))
    upmaps = osd_dump['pg_upmap_items']
  except (ValueError, KeyError):
    eprint('Error loading existing upmaps')
    sys.exit(1)
  UP = set(o['osd'] for o in osd_dump.get('osds', []) if o.get('up'))

  # discover the crush tree, the failure domain of each rule and the rule each
  # pool uses
  try:
    crush = json.loads(get_cluster_output('ceph osd crush dump -f json',
                                          {"prefix": "osd crush dump", "format": "json"}))
  except ValueError:
    eprint('Error loading the crush map')
    sys.exit(1)
  build_topology(crush, osd_dump)

  # discover pools replicated or erasure
  pool_type = {}
  try:
    osd_pool_ls_detail = get_cluster_output('ceph osd pool ls detail',
                                            {"prefix": "osd pool ls", "detail": "detail", "format": "plain"})
    for line in osd_pool_ls_detail.split('\n'):
      if line.startswith('pool '):
        x = line.split(' ')
        pool_type[x[1]] = x[3]
  except IndexError:
    eprint('Error parsing pool types')
    sys.exit(1)

  # the pg-upmap-items each pg already carries, if any
  upmap_by_pgid = dict((str(u['pgid']), u.get('mappings', [])) for u in upmaps)

  # handle each remapped pg
  print(r'while ceph status | grep -q "peering\|activating\|laggy"; do sleep 2; done')
  num = 0
  for pg in remapped:
    if num == 50:
      print(r'wait; sleep 4; while ceph status | grep -q "peering\|activating\|laggy"; do sleep 2; done')
      num = 0

    if options.ignore_backfilling and "backfilling" in pg['state']:
      continue

    pgid = str(pg['pgid'])
    pool = pgid.split('.')[0]
    if pool not in pool_type:
      # the pool was deleted between reading the pgs and reading the pools
      eprint('Skipping pg %s of unknown pool %s' % (pgid, pool))
      continue
    if pool_type[pool] not in ('replicated', 'erasure'):
      eprint('Unknown pool type for %s' % pool)
      sys.exit(1)

    # work from the mapping crush produces, not from the one the pg already
    # carries, because that is what pg-upmap-items is expressed against
    items = upmap_by_pgid.get(pgid, [])
    raw = reverse_upmap(pg['up'], items) if items else pg['up']

    pairs = gen_upmap(raw, pg['acting'],
                      replicated=(pool_type[pool] == 'replicated'))

    # leave a pg which already carries exactly these items alone
    if items and pairs == [(m['from'], m['to']) for m in items]:
      continue

    # crush already maps the pg where it should be, so the items it carries are
    # the only thing making it remapped
    if not pairs:
      if items:
        rm_upmap_pg_items(pgid)
        num += 1
      continue

    # pg-upmap-items replaces the pg's items, so there is nothing to remove first
    upmap_pg_items(pgid, pairs)
    num += 1

  print(r'wait; sleep 4; while ceph status | grep -q "peering\|activating\|laggy"; do sleep 2; done')

if __name__ == '__main__':
  main()
