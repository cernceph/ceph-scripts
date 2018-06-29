#!/bin/bash


pidof ceph-osd && exit 

for db in /var/lib/ceph/osd/ceph-*/block.db
do
  dev=`readlink -f $db`
  osd=`dirname $db`
  echo "ceph-bluestore-tool set-label-key --key path_block.db --value ${dev} --dev ${osd}/block"
done
