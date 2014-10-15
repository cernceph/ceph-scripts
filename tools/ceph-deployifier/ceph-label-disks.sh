#!/bin/bash
#
# Used to convert an "old" cernceph|enovance/puppet-ceph prepared OSD to one that 
# looks like it was prepared by ceph-deploy, i.e. ceph-disk.
#
# ceph-disk list show look like this when you start:
#
# /dev/sdh :
#   /dev/sdh1 other, xfs, mounted on /var/lib/ceph/osd/osd.211
#
#
# This script relies on the existence of /etc/ceph/ceph.conf.new which has all
# the [osd.<id>] stanzas removed and these entries removed:
#
# [global]
#   keyring = /etc/ceph/keyring
#
# [osd]
#   osd data = ...
#   osd journal = ...
#

JOURNAL_UUID='45b0969e-9b03-4f30-b4c6-b4b80ceff106'
DMCRYPT_JOURNAL_UUID='45b0969e-9b03-4f30-b4c6-5ec00ceff106'
OSD_UUID='4fbd7e29-9d25-41b8-afd0-062c0ceff05d'
DMCRYPT_OSD_UUID='4fbd7e29-9d25-41b8-afd0-5ec00ceff05d'
TOBE_UUID='89c57f98-2fe5-4dc0-89c1-f3ad0ceff2be'
DMCRYPT_TOBE_UUID='89c57f98-2fe5-4dc0-89c1-5ec00ceff2be'


YYY=$1

echo
echo Checking SSD journal status...
lsscsi | grep INTEL
ceph-disk list | grep 'ceph journal'

if [ "${YYY}" != "--yyy" ]
then
    read -p "Are the SSDs on sda,sdb,sdc,sdd and already partitioned? " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]
    then
        exit 1
    fi
fi

read ODEV OPART OSD <<<$(ceph-disk list | grep '/var/lib/ceph/osd/osd' | head -n1 | awk '{ print substr($1,0,8) " " substr($1,9,1) " " substr($6,match($6,/osd\./),length($6)) }')
read JDEV JPART <<<$(ceph-disk list | grep 'ceph journal' | grep -v for | head -n1 | awk '{ print substr($1,0,8) " " substr($1,9,1) }')

if [ "${ODEV}" == "" ] || [ "${OPART}" == "" ] || [ "${OSD}" == "" ] || [ "${JDEV}" == "" ] || [ "${JPART}" == "" ]
then
    echo
    echo Detection failed. Exiting.
    echo [DEBUG] Detected ${OSD} on ${ODEV} ${OPART} will use journal ${JDEV} ${JPART}
    exit 1
fi

echo
echo "Detected ${OSD} on ${ODEV} ${OPART} will use journal ${JDEV} ${JPART}"

if [ "${YYY}" != "--yyy" ]
then
    read -p "Continue? " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]
    then
        exit 1
    fi
fi

ID=`cat /var/lib/ceph/osd/$OSD/whoami`
UUID=`cat /var/lib/ceph/osd/$OSD/fsid`
JUUID=`sgdisk -i $JPART $JDEV | grep 'Partition unique GUID' | awk '{print tolower($4)}'`

if [ "${ID}" == "" ] || [ "${UUID}" == "" ] || [ "${JUUID}" == "" ]
then
    echo
    echo Detection failed. Exiting.
    echo [DEBUG] Detected ID:${ID} UUID: ${UUID} JUUID: ${JUUID}
    exit 1
fi


echo
echo "Detected ID:${ID} UUID: ${UUID} JUUID: ${JUUID}"
if [ "${YYY}" != "--yyy" ]
then
    read -p "Continue? " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]
    then
        exit 1
    fi
fi


echo
echo Symlinking $OSD to ceph-${ID}
cd /var/lib/ceph/osd
ln -s $OSD ceph-$ID
cd ceph-$ID


echo
echo Touching active, sysvinit, journal_uuid files
echo 'ok' > active
touch sysvinit
echo $JUUID > journal_uuid


echo
echo Stopping OSD $OSD
service ceph stop $OSD


echo
echo Flushing journal for ID $ID
ceph-osd -i $ID --flush-journal


echo
echo "Going to run sgdisk --change-name=${OPART}:'ceph data' --partition-guid=${OPART}:${UUID} --typecode=${OPART}:${OSD_UUID} -- ${ODEV}"
if [ "${YYY}" != "--yyy" ]
then
    read -p "Continue? " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]
    then
        exit 1
    fi
fi
sgdisk --change-name=$OPART:'ceph data' --partition-guid=$OPART:$UUID --typecode=$OPART:$OSD_UUID -- $ODEV


echo
echo Symlinking to new journal /dev/disk/by-partuuid/$JUUID
mv journal journal.orig
ln -s /dev/disk/by-partuuid/$JUUID journal


echo
echo Getting a new ceph.conf
mv /etc/ceph/ceph.conf /etc/ceph/ceph.conf.orig
cp /etc/ceph/ceph.conf.new /etc/ceph/ceph.conf


echo
echo Making new journal
ceph-osd -i $ID --mkjournal


echo
echo Unmounting and removing $OSD dirs
cd ../
rm -f ceph-$ID
umount $OSD
rmdir $OSD


echo
echo Triggering udev
udevadm trigger --subsystem-match="block"
udevadm settle


echo
echo Checking $OSD status
service ceph status $OSD


echo
echo Restoring old ceph.conf
mv -f /etc/ceph/ceph.conf.orig /etc/ceph/ceph.conf


echo
echo Done.
