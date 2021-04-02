#!/usr/bin/env python3
#
# Hacked by: Dan van der Ster <daniel.vanderster@cern.ch>

import argparse
import json
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument("-p", "--pool", help="consider this pool only",
                    type=int)
args = parser.parse_args()

def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

def rm_upmap_pg_items(pgid):
  print('ceph osd rm-pg-upmap-items %s &' % pgid)

def doexit():
    eprint("Waiting for stable PGs...")
    print('wait; sleep 4; while ceph status | grep -q "peering\|activating"; do sleep 2; done')
    sys.exit(0)

# start here

# discover osd fullness
osd_df_json = subprocess.check_output(['ceph', 'osd', 'df', '-f', 'json'])  
osd_df = json.loads(osd_df_json)
nodes = osd_df['nodes']

in_osds = list(filter(lambda x: x['reweight'] > 0, nodes))
osds = sorted(in_osds, key=lambda x: x['utilization'])

eprint("Most full: osd.%d %.3f%%" % (osds[-1]['id'], osds[-1]['utilization']))
eprint("Least full: osd.%d %.3f%%" % (osds[0]['id'], osds[0]['utilization']))

if osds[-1]['utilization'] - osds[0]['utilization'] < 5:
  eprint("OSDs sufficiently balanced, exiting")
  sys.exit(0)

# discover existing upmaps
osd_dump_json = subprocess.check_output(['ceph', 'osd', 'dump', '-f', 'json'])  
osd_dump = json.loads(osd_dump_json)
upmaps = osd_dump['pg_upmap_items']

# parse all upmaps *from* each osd
upmaps_from_osd = {}
for u in upmaps:
    pgid = u['pgid']
    if args.pool and int(pgid.split('.')[0]) != args.pool:
        continue
    for m in u['mappings']:
        try:
            upmaps_from_osd[m['from']].append(pgid)
        except KeyError:
            upmaps_from_osd[m['from']] = [pgid,]

# safety wait
eprint("Waiting for stable PGs...")
print('while ceph status | grep -q "peering\|activating"; do sleep 2; done')

# remove 30 upmaps
to_go = 30
pgs_removed = []
for osd in osds:
    eprint("Handling osd.%d (%.3f%% full)" % (osd['id'], osd['utilization']))
    osdid = osd['id']
    per_osd_to_go = 4
    if osdid not in upmaps_from_osd:
        eprint('No upmaps from osd.%d found!' % (osdid))
        continue
    for pgid in upmaps_from_osd[osdid]:
        if pgid not in pgs_removed:
            rm_upmap_pg_items(pgid)
            pgs_removed.append(pgid)
            to_go -= 1
            per_osd_to_go -= 1
            if to_go == 0:
                doexit()
            if per_osd_to_go == 0:
                break

doexit()
