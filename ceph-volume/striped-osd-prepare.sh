#!/bin/bash

[ -z "$DISKS" ] && DISKS=48
lvols=$((100*2/$DISKS))

ls -l $@ | awk '{ print $10 }' | \
while read d1; read d2; do
        echo ceph-volume lvm zap $d1
        echo ceph-volume lvm zap $d2
        vgname=ceph-`uuid -v4`
        lvname=osd-`uuid -v4`
        cname=cache-`uuid -v4`
        echo vgcreate $vgname $d1 $d2
        echo lvcreate -i 2 -l 100%FREE -n $lvname $vgname
        echo lvcreate -l $lvols%VG -n $cname cephrocks
        echo ceph-volume lvm create --bluestore --data $vgname/$lvname --block.db cephrocks/$cname #--block.wal cephrocks/$cname
done
