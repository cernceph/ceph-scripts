#!/bin/bash -x
# Used to chown all Ceph OSD files, which is a needed step for
# a hammer to jewel upgrade.

chown_osd () {
  DIR=$1
  ID=$(cat ${DIR}/whoami) || (echo ${1} is not mounted && return 1)

  echo "starting 1st chown on osd.${ID} (while ceph-osd is running)"
  time ionice -c3 chown -R ceph:ceph ${DIR}
  echo "stopping osd.${ID}"
  systemctl stop ceph-osd@${ID}.service
  echo "starting 2nd chown on osd.${ID} (while ceph-osd is stopped)"
  time find ${DIR} ! -user ceph -print0 | xargs -0 -n 100 chown ceph:ceph
  echo "starting osd.${ID}"
  systemctl start ceph-osd@${ID}.service  
  echo "done with osd.${ID}"
}

puppet agent --disable 'chown intervention'

chown ceph:ceph /var/log/ceph /var/lib/ceph /var/lib/ceph/* /var/lib/ceph/tmp/* /var/lib/ceph/boot*/* /var/run/ceph

# find all osds, chown ceph:ceph, then stop the osd, chown a 2nd time, then start the OSD.
for OSD in $(find /var/lib/ceph/osd -maxdepth 1 -mindepth 1 -type d -user root)
do
  ID=$(cat ${OSD}/whoami || echo 0)
  chown_osd ${OSD} &> /var/log/ceph/chown-osd.${ID}.log &
done

wait

# partprobe to recreate journal devs owned by ceph
partprobe

echo all done. Set puppet ceph user/group to ceph:ceph before re-enabling puppet. 
