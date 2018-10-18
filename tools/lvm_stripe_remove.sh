FAILED_DEV=$1

OUT=`mktemp`

lvs -o vg_name,devices,lv_tags | grep "$FAILED_DEV\b" | grep -Po 'osd_id=[0-9]*|ceph-.+? |/dev/[sv]d[a-z]+|cephrocks.+?(?=,)' > $OUT

if [[ ! -s $OUT ]]; then
	rm -f $OUT
	echo "Disk not used by lvm"
	exit 0
fi

cat $OUT

#Out file contents:
#1 vg_name
#2 first disk
#3 second disk
#4 rocks db lvm
#5 osd id

OSD_ID=`grep osd_id $OUT | grep -Po '[0-9]+'`

#Stop ceph process
systemctl stop ceph-osd@$OSD_ID

sleep 5s

#Destroy the osd
ceph osd out $OSD_ID
ceph osd destroy $OSD_ID --yes-i-really-mean-it

#Unmount the osd
umount /var/lib/ceph/osd/ceph-$OSD_ID

#Remove the vg (removes logical volumes also in that group)
vgremove -y `head -n1 < $OUT`

#Remove rocks db lvm
lvremove -y `grep cephrocks $OUT`

#Remove stripe devices that are in the second and third line
pvremove -y `sed -n '2,3p' $OUT`

#clear the disks (dd if=/dev/zero...)
ceph-volume lvm zap `sed -n 2p $OUT`
ceph-volume lvm zap `sed -n 3p $OUT`

rm -f $OUT
