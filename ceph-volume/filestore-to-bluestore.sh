#!/bin/bash

echo "This script will ERASE this host's osds from the cluster" \
     "and make new ones with the bluestore format"
read -p "Are you sure you want to proceed? (y/n): " -r
case $REPLY in
  y ) echo "Starting osd removal operation.";;
  * ) echo "Exiting..."; exit 0;;
esac

disks=($(ceph-disk list | grep 'ceph data' | awk '{ print substr($1, 0, length($1)-1) }'))
osds=($(ceph-disk list | grep -oP '(?<=osd\.)[0-9]{0,5}'))

for i in ${!osds[@]};
do
  echo ceph osd out ${osds[i]}
  echo systemctl stop ceph-osd@${osds[i]}
  echo sleep 5s
  echo ceph auth del osd.${osds[i]}
  echo ceph osd rm ${osds[i]}
  echo ceph-volume lvm zap ${disks[i]}
  echo ceph-volume lvm create --bluestore --osd-id ${osds[i]} --data ${disks[i]}
  echo sleep 6h
done
