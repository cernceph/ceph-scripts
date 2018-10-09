#!/usr/bin/env python

import json, commands, sys

def gen_upmap(up, acting):
  u = set(up)
  a = set(acting)
  assert(len(u) == len(a))
  lhs = u - a
  rhs = a - u
  assert(len(lhs) == len(rhs))
  return zip(lhs, rhs)

def upmap_pg_items(pgid, mapping):
  print 'ceph osd pg-upmap-items %s' % pgid,
  for pair in mapping:
    print '%s %s ' % pair,
  print '&'

def rm_upmap_pg_items(pgid):
  print 'ceph osd rm-pg-upmap-items %s &' % pgid

try:
  remapped_json = commands.getoutput('ceph pg ls remapped -f json')
  remapped = json.loads(remapped_json)
except ValueError:
  sys.exit(0)

osd_dump_json = commands.getoutput('ceph osd dump -f json')
osd_dump = json.loads(osd_dump_json)
upmaps = osd_dump['pg_upmap_items']

has_upmap = {}
for pg in upmaps:
   pgid = str(pg['pgid'])
   has_upmap[pgid] = True

for pg in remapped:
  pgid = pg['pgid']
  try:
    if has_upmap[pgid]:
      rm_upmap_pg_items(pgid)
      continue
  except KeyError:
    pass
  up = pg['up']
  acting = pg['acting']
  pairs = gen_upmap(up, acting)
  upmap_pg_items(pgid, pairs)
