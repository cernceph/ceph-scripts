#!/bin/bash
#
# Used to prepare our INTEL DCS3700 SSDs to look like ceph-deployed journals.
# 

JOURNAL_UUID='45b0969e-9b03-4f30-b4c6-b4b80ceff106'

lsscsi | grep INTEL
ceph-disk list | grep 'ceph journal'

read -p "Will modify sda sdb sdc sdd. Continue? " -n 1 -r
echo    # (optional) move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi


for disk in sda sdb sdc sdd; do
  for i in {1..5}; do
    sgdisk --new=$i:0:+20480M --change-name=$i:'ceph journal' --partition-guid=$i:`uuid -v4` --typecode=$i:$JOURNAL_UUID --mbrtogpt -- /dev/$disk
  done
done
