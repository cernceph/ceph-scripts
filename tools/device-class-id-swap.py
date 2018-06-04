#!/usr/bin/env python

import argparse, re, sys
from subprocess import Popen, PIPE

parser = argparse.ArgumentParser(description='Change ceph osd tree ids to avoid device class data movement')
parser.add_argument('file', help='crush map file')
args = parser.parse_args()

re_id1 = re.compile(r'(id\s+)(-?\d+)')
re_id2 = re.compile(r'(id\s+)(-?\d+)(\s+class\s+hdd)')

with open(args.file, 'r') as ifile:
    with open(args.file+'-new', 'w') as ofile:
        while True:
            line1 = ifile.readline()
            if not line1: break

            res1 = re_id1.search(line1)
            if res1:
                id1 = res1.group(2)
                line2 = ifile.readline()
                if not line2:
                    print "Can't find hdd class after bucket id"
                    sys.exit(1)
                else:
                    res2 = re_id2.search(line2)
                    if res2:
                        id2 = res2.group(2)
                        ofile.write(re_id1.sub("\\1"+id2      , line1))
                        ofile.write(re_id2.sub("\\1"+id1+"\\3", line2))
                    else:
                        ofile.write(line1)
                        ofile.write(line2)
            else:
                ofile.write(line1)
