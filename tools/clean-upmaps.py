#!/usr/bin/env python

# this script looks at all pg_upmap_items and checks if 
# any have the same osd twice in the from or to set

import json, commands, sys

osd_dump_json = commands.getoutput('ceph osd dump -f json')
osd_dump = json.loads(osd_dump_json)
upmaps = osd_dump['pg_upmap_items']

for pg in upmaps:
  pgid = str(pg['pgid'])
  f = [x['from'] for x in pg['mappings']]
  t = [x['to'] for x in pg['mappings']]
  if len(f) != len(set(f)) or len(t) != len(set(t)):
    print pgid,'has osds duplicated in the from or to set',pg['mappings']
