#!/usr/bin/env python

import json
import commands
from optparse import OptionParser


parser = OptionParser()
parser.add_option("--iops_rd", dest="iops_rd", default=100, type="int",
                  help="Read IOPS")
parser.add_option("--iops_wr", dest="iops_wr", default=100, type="int",
                  help="Write IOPS")
parser.add_option("--bps_rd", dest="bps_rd", default=80000000, type="int",
                  help="Read BPS")
parser.add_option("--bps_wr", dest="bps_wr", default=80000000, type="int",
                  help="Write BPS")
parser.add_option("--doit", dest="doit", action="store_true", default=False,
                  help="Change the throttles to the correct values if needed")

(options, args) = parser.parse_args()

for instance in commands.getoutput("virsh list | grep running | awk '{print $2}'").split():
  print "Checking", instance, "..."
  block_json = commands.getoutput("virsh qemu-monitor-command %s '{\"execute\":\"query-block\"}'" % instance)
  blocks = json.loads(block_json)['return']
  for block in blocks:
    if block['inserted']['file'].startswith('rbd'):
      device = block['device']
      iops_rd = block['inserted']['iops_rd']
      iops_wr = block['inserted']['iops_wr']
      bps_rd = block['inserted']['bps_rd']
      bps_wr = block['inserted']['bps_wr']
      print " ", device, "is RBD, current thottle: %d/%d/%d/%d" % (iops_rd, iops_wr, bps_rd, bps_wr),
      if iops_rd != options.iops_rd or iops_wr != options.iops_wr or bps_rd != options.bps_rd or bps_wr != options.bps_wr:
        if options.doit:
          cmd = 'virsh qemu-monitor-command %s \'{"execute":"block_set_io_throttle","arguments":{"device":"%s","iops":0,"iops_rd":%d,"iops_wr":%d,"bps":0,"bps_rd":%d,"bps_wr":%d}}\'' % (instance, device, options.iops_rd, options.iops_wr, options.bps_rd, options.bps_wr)
          print "...", cmd
        else:
          print "... Need to throttle. Run again with --doit"
      else:
          print "... All good :)"
