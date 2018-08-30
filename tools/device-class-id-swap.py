#!/usr/bin/env python

import argparse, re, sys
from subprocess import Popen, PIPE

parser = argparse.ArgumentParser(description='Change ceph osd tree ids to avoid device class data movement')
parser.add_argument('file', help='crush map file')
args = parser.parse_args()

re_id1 = re.compile(r'(\s+id\s+)(-?\d+)')
re_id2 = re.compile(r'(\s+id\s+)(-?\d+)(\s+class\s+(ssd|hdd))')
re_id3 = re.compile(r'(\s+bucket_id\s+)(-?\d+)')

change_map = {}

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
                        ssd_first = False
                        if 'hdd' in res2.group(3):
                            id2 = res2.group(2)
                        elif 'ssd' in res2.group(3):
                            ssd_first = True
                            line3 = ifile.readline()
                            res3 = re_id2.search(line3)
                            if res3:
                                id2 = res3.group(2)
                        change_map[id1] = id2
                        ofile.write(re_id1.sub("\\1"+id2      , line1))
                        if ssd_first:
                            ofile.write(line2)
                            ofile.write(re_id2.sub("\\1"+id1+"\\3", line3))
                        else:
                            ofile.write(re_id2.sub("\\1"+id1+"\\3", line2))
                    else:
                        ofile.write(line1)
                        ofile.write(line2) 
            else:
                res = re_id3.search(line1)
                if res:
                    id = res.group(2)
                    if id in change_map:
                        ofile.write(re_id3.sub("\\1"+change_map[id], line1))
                        continue
                ofile.write(line1)
