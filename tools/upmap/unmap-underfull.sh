#!/bin/bash

UNDERFULL=`ceph osd df | grep 'hdd 5.45798  1.00000' | sort -k8 -n | head -n4 | awk '{print $1}'`

for osd in $UNDERFULL
do
  echo Unmapping $osd ...
  ceph osd dump | grep pg_upmap_items | egrep "\[${osd},[0-9]+\]" | awk '{print "ceph osd rm-pg-upmap-items", $2, "&"}'
done
