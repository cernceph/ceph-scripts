#!/usr/bin/env python3

# this script looks at all pg_upmap_items and checks if
# any have the same osd twice in the from or to set

import json, subprocess, sys


def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)


osd_dump_json = subprocess.getoutput('ceph osd dump -f json | jq -r')
osd_dump = json.loads(osd_dump_json)
upmaps = osd_dump['pg_upmap_items']

pgs_json = subprocess.getoutput('ceph pg ls -f json | jq -r')
pgs = json.loads(pgs_json)

cmd_out = subprocess.getoutput('ceph osd crush rule dump -f json | jq -r \'.[] as $k | "\($k.rule_id) \($k.steps[-2].type)"\'')
crush_rule_failure_domains = dict(item.split() for item in cmd_out.split('\n'))

pools = {}
for pool in osd_dump['pools']:
  pool['failure_domain'] = crush_rule_failure_domains[str(pool['crush_rule'])]
  pools[str(pool['pool'])] = pool #pool pool pool

nodes = {}
for node in json.loads(subprocess.getoutput('ceph osd tree -f json | jq -r'))['nodes']:
  if node['id'] in nodes:
    nodes[node['id']].update(node)
  else:
    nodes[node['id']] = node
  if 'children' in node:
    for child in node['children']:
      parent_info = {'parent': node['id']}
      if child in nodes:
        nodes[child].update(parent_info)
      else:
        nodes[child] = parent_info

# nautilus compat
try:
  _pgs = pgs['pg_stats']
  pgs = _pgs
except TypeError:
  pass

up = {}
for pg in pgs:
  up[pg['pgid']] = pg['up']

def lookup_parent_id(osd, nodes, _type="host"):
    parent = nodes[osd]
    while parent['type'] != _type:
        parent = nodes[parent['parent']]
    return parent['id']

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

for pg in upmaps:
  pgid = str(pg['pgid'])
  pool = pgid.split('.')[0]
  if pool_type[pool] == 'replicated':
    replicated = True
    erasure = False
  elif pool_type[pool] == 'erasure':
    replicated = False
    erasure = True
  else:
    eprint('unknown pool type for %s' % pgid)
    sys.exit(1)

  rm = False
  f = [x['from'] for x in pg['mappings']]
  t = [x['to'] for x in pg['mappings']]
  if len(f) != len(set(f)) or len(t) != len(set(t)):
    print(pgid, 'upmap has osds duplicated in the from or to set', pg['mappings'])
    rm = True
  if replicated and len(f+t) != len(set(f+t)):
    print(pgid, 'upmap has osds duplicated:', pg['mappings'])
    rm = True
  for x in pg['mappings']:
    if x['to'] not in up[pgid]:
      print(pgid, 'upmap has "to" osds which are not in the up set', pg['mappings'])
      rm = True
  failure_domain_nodes = [lookup_parent_id(osd, nodes, pools[pgid.split('.')[0]]['failure_domain']) for osd in up[pgid]]
  if len(failure_domain_nodes) != len(set(failure_domain_nodes)):
    print(pgid, 'upmap does not follow the crush rule on failure domain', pg['mappings'], up[pgid], [nodes[fdn]['name'] for fdn in failure_domain_nodes])
    rm = True
  if rm:
    print('ceph osd rm-pg-upmap-items', pgid)
