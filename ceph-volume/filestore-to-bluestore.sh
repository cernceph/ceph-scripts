#!/bin/bash

echo "This script will ERASE this host's osds from the cluster" \
     "and make new ones with the bluestore format"
read -p "Are you sure you want to proceed? (y/n): " -r
case $REPLY in
  y ) echo "Starting osd removal operation.";;
  * ) echo "Exiting..."; exit 0;;
esac

disks=($(df | grep ceph | awk '{ print substr($1, 0, length($1)-1) }'))
osds=($(df | grep -oP "(?<=ceph-)[0-9]{1,5}"))

for i in ${!osds[@]};
do
  echo ceph osd out ${osds[i]}
  echo systemctl stop ceph-osd@${osds[i]}
  echo sleep 5s
  echo ceph osd purge ${osds[i]}
  echo ceph-volume lvm zap ${disks[i]}
  echo ceph-volume lvm create --bluestore --osd-id ${osds[i]} --data ${disks[i]}
  echo sleep 6h
done
