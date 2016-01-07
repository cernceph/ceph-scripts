#!/usr/bin/python

import simplejson as json
import commands
import time

MAX_SCRUBS = 50
SLEEP = 30

while(True):

  print "Dumping pg info."
  output = commands.getoutput('ceph pg dump -f json 2>/dev/null')
  print "Loading pg stats json."
  pg_dump = json.loads(output)
  pg_stats = pg_dump['pg_stats']

  # Which PGs are scrubbing?
  pgs_scrubbing = [ pg for pg in pg_stats if 'scrubbing' in pg['state'] ]
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

  n_to_trigger = MAX_SCRUBS - n_scrubbing
  if n_to_trigger > 0:
    n_triggered = 0
    print
    print "Should trigger %d deep scrubs" % n_to_trigger
    print
    print "PGs least recently deep scrubbed:"
    for pg in pgs_scrubbing_stale:
      if n_triggered == n_to_trigger:
        break
      print '  ', pg['pgid'], 'last deep scrubbed', pg['last_deep_scrub_stamp'], 
      print 'last scrubbed', pg['last_scrub_stamp'],
      blocked = False
      for osd in pg['acting']:
        if osd in osds_scrubbing.keys():
          print '(blocked by OSD', osd, ')',
          blocked = True
      if not blocked:
        output = commands.getoutput('ceph pg deep-scrub %s' % pg['pgid'])
        print output,
        n_triggered += 1
      print
  else:
    print
    print 'Already', n_scrubbing, 'scrubs in progress.'

  print
  print "Sleeping %d seconds..." % SLEEP
  time.sleep(SLEEP)
  print
