#!/usr/bin/python

try: import simplejson as json
except ImportError: import json

import commands
import time
import argparse
import rados

parser = argparse.ArgumentParser(description='Discover ceph OSDs which have not yet been prepared and prepare them.')
parser.add_argument('--max-scrubs', dest='MAX_SCRUBS', type=int, default=0,
                    help='Maximum number of scrubs to trigger (default: %(default)s)')
parser.add_argument('--sleep', dest='SLEEP', type=int, default=0,
                    help='Sleep this many seconds then run again, looping forever. 0 disables looping. (default: %(default)s)')
parser.add_argument('--conf', dest='CONF', type=str, default="/etc/ceph/ceph.conf",
                    help='Ceph config file. (default: %(default)s)')

args = parser.parse_args()
MAX_SCRUBS = args.MAX_SCRUBS
SLEEP = args.SLEEP
CONF = args.CONF

# Connect to cluster
try:
  cluster = rados.Rados(conffile=CONF)
except TypeError as e:
  print 'Argument validation error: ', e
  raise e

try:
  cluster.connect()
except Exception as e:
  print "connection error: ", e
  raise e

while(True):

  print "Dumping pg info."

  cmd = {'prefix': 'pg dump', 'format': 'json'}
  ret, buf, out = cluster.mon_command(json.dumps(cmd), b'', timeout=5)

  print "Loading pg stats json."
  pg_dump = json.loads(buf)
  pg_stats = pg_dump['pg_stats']

  # Which PGs are scrubbing?
  pgs_scrubbing = [ pg for pg in pg_stats if 'scrubbing' in pg['state'] ]
  pgs_scrubbing.sort(key=lambda k: k['pgid'])
  print
  print "PGs Scrubbing:"
  for pg in pgs_scrubbing:
    print '  ', pg['pgid'], 'last scrubbed', pg['last_scrub_stamp'],
    print 'on osds', ' '.join(str(o) for o in pg['acting'])

  n_scrubbing = len(pgs_scrubbing)

  # Which OSDs are scrubbing?
  osds_scrubbing = {}
  for pg in pgs_scrubbing:
    for osd in pg['acting']:
      try:
        osds_scrubbing[osd] += 1
      except KeyError:
        osds_scrubbing[osd] = 1

  print
  print "OSDs scrubbing (%s in total): " % len(osds_scrubbing.keys())
  print '  ',
  print ', '.join(str(o) for o in sorted(osds_scrubbing.keys()))

  #for osd, n in osds_scrubbing.iteritems():
  #  print '  ', osd, '(%d scrubs)' % n

  # Which PGs are next to be scrubbed?
  pg_stats.sort(key=lambda k: k['last_scrub_stamp'])
  pgs_scrubbing_next = [pg for pg in pg_stats if 'scrubbing' not in pg['state'] ][:10]
  pgids_scrubbing_next = [pg['pgid'] for pg in pgs_scrubbing_next]

  print
  print "PGs next to be scrubbed:"
  print "   (PGs scheduled after now - osd_scrub_min_interval will wait until then.)"
  print "   (PGs scheduled before now - osd_scrub_min_interval are blocked by osd_max_scrubs or waiting for loadavg < osd_scrub_load_threshold)"
  print
  for pg in pgs_scrubbing_next:
    print '  ', pg['pgid'], 'last scrubbed', pg['last_scrub_stamp'],
    print 'on osds', ' '.join(str(o) for o in pg['acting']),
    for osd in pg['acting']:
      if osd in osds_scrubbing.keys():
        print '(blocked by OSD', osd, ')',
    print


  # Which PGs have not been deep scrubbed the longest?
  pg_stats.sort(key=lambda k: k['last_deep_scrub_stamp'])
  pgs_scrubbing_stale = [pg for pg in pg_stats if 'scrubbing' not in pg['state'] ][:100]

  n_to_trigger = max(0, MAX_SCRUBS - n_scrubbing)

  i = 0
  n_triggered = 0
  print
  print "Should trigger %d deep scrubs" % n_to_trigger
  print
  print "PGs least recently deep scrubbed:"
  for pg in pgs_scrubbing_stale:
    i += 1
    print '  ', pg['pgid'], 'last deep scrubbed', pg['last_deep_scrub_stamp'],
    print 'last scrubbed', pg['last_scrub_stamp'],
    blocked = False
    for osd in pg['acting']:
      if osd in osds_scrubbing.keys():
        print '(blocked by OSD', osd, ')',
        blocked = True
    if not blocked and n_to_trigger > 0:
      output = commands.getoutput('ceph pg deep-scrub %s' % pg['pgid'])
      print output,
      n_triggered += 1
      if n_triggered == n_to_trigger:
        break
    print
    if n_to_trigger < 1 and i == 10:
      break

  if SLEEP:
    print
    print "Sleeping %d seconds..." % SLEEP
    time.sleep(SLEEP)
    print
  else:
    break

# Disconnect
cluster.shutdown()
