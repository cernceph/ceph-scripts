#!/usr/bin/env python

# this script looks at all pg_upmap_items and checks if 
# any have the same osd twice in the from or to set

import json, commands, sys

osd_dump_json = commands.getoutput('ceph osd dump -f json')
osd_dump = json.loads(osd_dump_json)
upmaps = osd_dump['pg_upmap_items']

pgs_json = commands.getoutput('ceph pg ls -f json')
pgs = json.loads(pgs_json)

up = {}
for pg in pgs:
  up[pg['pgid']] = pg['up']

for pg in upmaps:
  pgid = str(pg['pgid'])
  f = [x['from'] for x in pg['mappings']]
  t = [x['to'] for x in pg['mappings']]
  if len(f) != len(set(f)) or len(t) != len(set(t)):
    print pgid, 'upmap has osds duplicated in the from or to set', pg['mappings']
  if len(f+t) != len(set(f+t)):
    print pgid, 'upmap has osds duplicated:', pg['mappings']
  for x in pg['mappings']:
    if x['to'] not in up[pgid]:
      print pgid, 'upmap has "to" osds which are not in the up set', pg['mappings']
