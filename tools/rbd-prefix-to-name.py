#!/usr/bin/python

from optparse import OptionParser
import sys
import re
import commands

def rbd_prefix_to_name(options):
  prefix = options.prefix.replace('rbd_data.','id_')
  pool = options.pool
  cmd = 'rados getomapval -p %s rbd_directory %s | grep \'^[0-9]\'' % (pool, prefix)
  output = commands.getoutput(cmd)
  name = ''
  lines = [x.strip() for x in output.split("\n")]
  for line in lines:
    all = re.findall(r'[A-Za-z0-9\-]+', line)
    if all:
      name += all[-1]
  return name

#[09:51][root@cephmon0 (production:beesly/mon*1) ~]# rados getomapval -p volumes rbd_directory id_1a871195a024a98 -o volnam
# (length 47) : 0000 : 2b 00 00 00 76 6f 6c 75 6d 65 2d 63 62 35 36 34 : +...volume-cb564
#0010 : 34 33 36 2d 35 33 32 32 2d 34 61 32 36 2d 61 38 : 436-5322-4a26-a8
#0020 : 61 31 2d 30 33 64 61 30 64 65 61 65 36 63 33    : a1-03da0deae6c3

if __name__ == "__main__":
  parser = OptionParser()
  parser.add_option("-P", "--prefix", dest="prefix", type="string",
                  help="RBD object prefix to lookup")
  parser.add_option("-p", "--pool", dest="pool", type="string", default="volumes",
                  help="Ceph pool (default: volumes)")
  (options, args) = parser.parse_args()
  if not options.prefix:
    parser.error('PREFIX not given')

  print rbd_prefix_to_name(options)
