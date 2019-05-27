#!/bin/bash

echo killall ceph-osd
echo systemctl stop ceph-osd.target
echo sleep 10
for OSD in /var/lib/ceph/osd/ceph-*;
do
  ID=`cat ${OSD}/whoami`
  echo "ceph-kvstore-tool bluestore-kv ${OSD} compact &> /var/log/ceph/compact.${ID}.log &"
done
echo wait
echo systemctl start ceph-osd.target
