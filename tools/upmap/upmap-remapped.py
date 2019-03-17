#!/usr/bin/env python
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

from __future__ import print_function
import json, commands, sys

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def gen_upmap_replicated(up, acting):
  u = set(up)
  a = set(acting)
  assert(len(u) == len(a))
  lhs = u - a
  rhs = a - u
  assert(len(lhs) == len(rhs))
  return zip(lhs, rhs)

def gen_upmap_erasure(up, acting):
  assert(len(up) == len(acting))
  mappings = []
  for pair in zip(up, acting):
    if pair[0] != pair[1]:
      mappings.append(pair)
  return mappings

def upmap_pg_items(pgid, mapping):
  print('ceph osd pg-upmap-items %s ' % pgid, end='')
  for pair in mapping:
    print('%s %s ' % pair, end='')
  print('&')

def rm_upmap_pg_items(pgid):
  print('ceph osd rm-pg-upmap-items %s &' % pgid)


# start here

# discover degraded pgs (we won't upmap any degraded pgs)
try:
  degraded_json = commands.getoutput('ceph pg ls degraded -f json')
  degraded = json.loads(degraded_json)
except ValueError:
  degraded = []

# save their pgids for later
degraded_pgids = []
for pg in degraded:
  degraded_pgids.append(pg['pgid'])

# discover remapped pgs
try:
  remapped_json = commands.getoutput('ceph pg ls remapped -f json')
  remapped = json.loads(remapped_json)
except ValueError:
  eprint('Error loading remapped pgs')
  sys.exit(1)

# discover existing upmaps
osd_dump_json = commands.getoutput('ceph osd dump -f json')
osd_dump = json.loads(osd_dump_json)
upmaps = osd_dump['pg_upmap_items']

# discover pools replicated or erasure
pool_type = {}
try:
  for line in commands.getoutput('ceph osd pool ls detail').split('\n'):
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
num_changed = 0
for pg in remapped:
  if num_changed % 50 == 0:
    print('wait')

  pgid = pg['pgid']

  # skip the degraded pgs
  if pgid in degraded_pgids:
    continue 
  
  try:
    if has_upmap[pgid]:
      rm_upmap_pg_items(pgid)
      num_changed += 1
      continue
  except KeyError:
    pass
  up = pg['up']
  acting = pg['acting']
  pool = pgid.split('.')[0]
  if pool_type[pool] == 'replicated':
    pairs = gen_upmap_replicated(up, acting)
  elif pool_type[pool] == 'erasure':
    pairs = gen_upmap_erasure(up, acting)
  else:
    eprint('Unknown pool type for %s' % pool)
    sys.exit(1)
  upmap_pg_items(pgid, pairs)
  num_changed += 1

print('wait')
