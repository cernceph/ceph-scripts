#!/usr/bin/env python

from cephinfo import cephinfo
import itertools
import random

# read the ceph PG and OSD info from the ceph-mon
cephinfo.init_pg()
cephinfo.init_osd()


osds = [ osd['osd'] for osd in cephinfo.get_osds_data() ]
triple_combinations = [ tuple(pg['acting']) for pg in cephinfo.get_pg_stats() ]

print "We have %d OSDs and %d PGs, hence %d combinations e.g. like this: %s" % (len(osds), cephinfo.get_n_pgs(), len(triple_combinations), triple_combinations[0])

nFailures = 0
nDataLoss = 0
nSimulations = 1000

print "Simulating %d triple failures" % nSimulations

for i in xrange(0,nSimulations):
  triple_failure = random.sample(osds, 3)

  nFailures += 1

  for order in itertools.permutations(triple_failure):
    if order in triple_combinations:
      nDataLoss += 1
      print "3 replica data loss incident with failure %s" % str(order)

  if nFailures % 1000 == 0:
    print "Simulated %d failures. Data loss incidents = %d." % (nFailures, nDataLoss)

print "End of simulation: Out of %d triple failures, %d caused a data loss incident" % (nFailures, nDataLoss)


print "\nSimulating %d double failures" % nSimulations
nFailures = 0
nOutage = 0

for i in xrange(0,nSimulations):
  double_failure = random.sample(osds, 2)

  nFailures += 1

  for pg in triple_combinations:
    if double_failure[0] in pg and double_failure[1] in pg:
      nOutage += 1
#      print "Data outage with failure OSDs %s and PG %s" % (double_failure, pg)

  if nFailures % 1000 == 0:
    print "Simulated %d failures. Data outage incidents = %d" % (nFailures, nOutage)

print "End of simulation: Out of %d double failures, %d caused a data outage incident" % (nFailures, nOutage)

print "\nSimulating %d double failures if downgraded to 2 replica RADOS" % nSimulations
double_combinations = [ tuple(pg['acting'][:2]) for pg in cephinfo.get_pg_stats() ]
nFailures = 0
nDataLoss = 0

for i in xrange(0,nSimulations):
  double_failure = random.sample(osds, 2)

  nFailures += 1

  for order in itertools.permutations(double_failure):
    if order in double_combinations:
      nDataLoss += 1
#      print "2 replica data loss incident with failure %s" % str(order)

  if nFailures % 1000 == 0:
    print "Simulated %d failures. Data loss incidents = %d." % (nFailures, nDataLoss)

print "End of simulation: Out of %d double failures, %d caused a data loss incident" % (nFailures, nDataLoss)


nSimulations = 10
for n in xrange(4, 21):
  nDataLoss = 0
  nFailures = 0
  print "\nSimulating %d %d-disk failures" % (nSimulations, n)
  for i in xrange(0,nSimulations):
    n_disk_failure = random.sample(osds, n)

    nFailures += 1
  
    for order in itertools.permutations(n_disk_failure, 3):
      if order in triple_combinations:
        nDataLoss += 1
        print "3 replica data loss incident with failure %s and PG %s" % (n_disk_failure, str(order))

    if nFailures % 1000 == 0:
      print "Simulated %d failures. Data loss incidents = %d." % (nFailures, nDataLoss)

  print "End of simulation: Out of %d %d disk failures, %d caused a data loss incident" % (nFailures, n, nDataLoss)
