#!/usr/bin/env python

from cephinfo import cephinfo
from optparse import OptionParser
from collections import defaultdict
import commands

def get_weight(osd, type='reweight'):
  return osd_weights[osd][type]

def change_weight(osd, new_weight, really):
  cmd = "ceph osd reweight %d %5f" % (osd, new_weight)
  print cmd
  if really:
    (status, output) = commands.getstatusoutput(cmd)
    if status:
      raise Exception('Non-zero exit status (%d) from command: %s %s' % (status, cmd, output))
  else:
    print "add --really to run the above command"

def reweight_by_utilization(oload, by_pg, pools, doit, really):
  if oload <= 100:
    raise Exception("You must give a percentage higher than 100.")
#      "The reweighting threshold will be calculated as <average-utilization> "
#      "times <input-percentage>. For example, an argument of 200 would "
#      "reweight OSDs which are twice as utilized as the average OSD.\n";

  cephinfo.init_pg()
  pgm = cephinfo.pg_data

  pgs_by_osd = defaultdict(int)

  if by_pg:
    weight_sum = 0.0
    num_pg_copies = 0
    num_osds = 0
    for p in pgm['pg_stats']:
      pool = p['pgid'].split('.')[0]
      if pools and pool not in pools:
         continue
      for a in p['acting']:
        if not pgs_by_osd[a]:
          num_osds += 1
          weight_sum += get_weight(a,'crush_weight')
          pgs_by_osd[a] = 0
        pgs_by_osd[a] += 1
        num_pg_copies += 1

    if not num_osds or (num_pg_copies / num_osds < 10):
      raise Exception('Refusing to reweight: we only have %d PGs across %d osds!' % (num_pg_copies, num_osds))

    average_util = num_pg_copies / weight_sum
    print "weight_sum: %3f, num_pg_copies: %d, num_osds: %d" % (weight_sum, num_pg_copies, num_osds)

  else:

    # Avoid putting a small number (or 0) in the denominator when calculating
    # average_util
    if pgm['osd_stats_sum']['kb'] < 1024:
      raise Exception("Refusing to reweight: we only have %d kB across all osds!" % pgm['osd_stats_sum']['kb'])

    if pgm['osd_stats_sum']['kb_used'] < 5 * 1024:
      raise Exception("Refusing to reweight: we only have %d kB across all osds!" % pgm['osd_stats_sum']['kb_used'])

    average_util = float(pgm['osd_stats_sum']['kb_used']) / float(pgm['osd_stats_sum']['kb'])

  # adjust down only if we are above the threshold
  overload_util = average_util * oload / 100.0

  # adjust weights up whenever possible
  underload_util = average_util # - (overload_util - average_util)

  print "average_util: %04f, overload_util: %04f, underload_util: %04f. " %(average_util, overload_util, underload_util)

  print "reweighted: "

  for osd in pgm['osd_stats']:
    if by_pg:
      util = pgs_by_osd[osd['osd']] / get_weight(osd['osd'],type='crush_weight')
    else:
      util = float(osd['kb_used']) / float(osd['kb'])

    # skip the OSDs that do not contain anything (probably a different crush root)
    if util < 0.01:
      continue

    if util >= overload_util:
      # Assign a lower weight to overloaded OSDs. The current weight
      # is a factor to take into account the original weights,
      # to represent e.g. differing storage capacities
      weight = get_weight(osd['osd'])
      new_weight = (average_util / util) * float(weight)
      print "%d (%4f >= %4f) [%04f -> %04f]" % (osd['osd'], util, overload_util, weight, new_weight)
      if doit: change_weight(osd['osd'], new_weight, really)
    if util <= underload_util:
      # assign a higher weight.. if we can
      weight = get_weight(osd['osd'])
      new_weight = (average_util / util) * float(weight)
      if new_weight > 1.0:
        new_weight = 1.0
      if new_weight > weight:
        print "%d (%4f <= %4f) [%04f -> %04f]" % (osd['osd'], util, underload_util, weight, new_weight)
        if doit: change_weight(osd['osd'], new_weight, really)

def get_weights():
  cephinfo.init_crush()
  global osd_weights

  osd_weights = dict()
 
  for osd in cephinfo.crush_data['nodes']:
    if osd['type'] == 'osd':
      id = osd['id']
      reweight = float(osd['reweight'])
      crush_weight = float(osd['crush_weight'])
      osd_weights[id] = dict()
      osd_weights[id]['crush_weight'] = crush_weight
      osd_weights[id]['reweight'] = reweight

if __name__ == "__main__":
  import sys
  parser = OptionParser()
  parser.add_option("-o", "--overload", dest="oload", type="float", default=120.0,
                  help="The overload threshold percentage, default 120%")
  parser.add_option("-b", "--by_pg", dest="by_pg", action="store_true",
                  help="Reweight by num PGs instead of utilization")
  parser.add_option("-p", "--pool", dest="pools", action="append",
                  help="Only work on these pools.")
  parser.add_option("-d", "--doit", dest="doit", action="store_true",
                  help="Do it!")
  parser.add_option("-r", "--really", dest="really", action="store_true",
                  help="Really really do it! This will change your crush map.")
  (options, args) = parser.parse_args()
  get_weights()
  reweight_by_utilization(options.oload, options.by_pg, options.pools, options.doit, options.really)
