#!/usr/bin/env python

from cephinfo import cephinfo
import itertools
import random

cephinfo.init_pg()
cephinfo.init_osd()

osds = [ osd['osd'] for osd in cephinfo.get_osds_data() ]
combinations = [ tuple(pg['acting']) for pg in cephinfo.get_pg_stats() ]

nPGs = cephinfo.get_n_pgs()

print "We have %d OSDs and %d PGs, hence %d combinations e.g. like this: %s" % (len(osds), nPGs, len(combinations), combinations[0])

nFailures = 0
nDataLoss = 0
nSimulations = 10000

print "Simulating %d failures" % nSimulations

for i in xrange(0,nSimulations):
  failure = random.sample(osds, 3)
  nFailures += 1
  for order in itertools.permutations(failure):
    if order in combinations:
      nDataLoss += 1
      print "Data loss incident with failure %s" % str(order)
  if nFailures % 1000 == 0:
    print "Simulated %d triple failures. Data loss incidents = %d" % (nFailures, nDataLoss)

print "\nEnd of simulation: Out of %d triple failures, %d caused a data loss incident" % (nFailures, nDataLoss)
