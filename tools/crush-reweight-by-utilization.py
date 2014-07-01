#!/usr/bin/env python

from cephinfo import cephinfo
from optparse import OptionParser

def reweight_by_utilization(oload):
  if oload <= 100:
    raise Exception("You must give a percentage higher than 100.")
#      "The reweighting threshold will be calculated as <average-utilization> "
#      "times <input-percentage>. For example, an argument of 200 would "
#      "reweight OSDs which are twice as utilized as the average OSD.\n";

  cephinfo.init_pg()
  pgm = cephinfo.pg_data

  # Avoid putting a small number (or 0) in the denominator when calculating
  # average_util
  if pgm['osd_stats_sum']['kb'] < 1024:
    raise Exception("Refusing to reweight: we only have %d kB across all osds!" % pgm['osd_stats_sum']['kb'])

  if pgm['osd_stats_sum']['kb_used'] < 5 * 1024:
    raise Exception("Refusing to reweight: we only have %d kB across all osds!" % pgm['osd_stats_sum']['kb_used'])

  average_util = float(pgm['osd_stats_sum']['kb_used']) / float(pgm['osd_stats_sum']['kb'])
  overload_util = average_util * oload / 100.0

  print "average_util: %04f, overload_util: %04f. " %(average_util, overload_util)

  print "overloaded osds: "
  changed = False

  for osd in pgm['osd_stats']:
    util = float(osd['kb_used']) / float(osd['kb'])
    if util >= overload_util:
      # Assign a lower weight to overloaded OSDs. The current weight
      # is a factor to take into account the original weights,
      # to represent e.g. differing storage capacities
      weight = osd_weights[osd['osd']]['crush_weight']
      new_weight = (average_util / util) * float(weight)
      print "%d [%04f -> %04f]" % (osd['osd'], weight, new_weight)


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
  parser.add_option("-o", "--oload", dest="oload", type="float",
                  help="The reweighting threshold will be calculated as <average-utilization>")
  (options, args) = parser.parse_args()
  if not options.oload:   # if filename is not given
    parser.error('OLOAD not given')
  get_weights()
  reweight_by_utilization(options.oload)
