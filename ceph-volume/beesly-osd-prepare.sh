ceph-volume lvm zap /dev/sd[a-x] /dev/sda[a-d] --destroy
ceph-volume lvm batch /dev/sd[a-f] /dev/sdaa --yes
ceph-volume lvm batch /dev/sd[g-l] /dev/sdab --yes
ceph-volume lvm batch /dev/sd[m-r] /dev/sdac --yes
ceph-volume lvm batch /dev/sd[s-x] /dev/sdad --yes
