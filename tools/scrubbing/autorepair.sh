#!/bin/bash

for PG in $(ceph pg ls inconsistent -f json | jq -r .[].pgid)
do
   echo Checking inconsistent PG $PG
   if ceph pg ls repair | grep -wq ${PG}
   then
      echo PG $PG is already repairing, skipping
      continue
   fi

   if grep -w ${PG} /var/log/ceph/ceph.log | grep -w ERR | grep -q 'candidate had a read error'
   then
      echo PG $PG seems auto-repairable, trying.
   else
      echo PG $PG is not auto-repairable, skipping.
      continue
   fi

   # disable other scrubs
   ceph osd set nodeep-scrub
   ceph osd set noscrub

   # bump up osd_max_scrubs
   ACTING=$(ceph pg $PG query | jq -r .acting[])
   for OSD in $ACTING
   do
      ceph tell osd.${OSD} injectargs -- --osd_max_scrubs=3
   done

   ceph pg repair $PG

   sleep 10

   for OSD in $ACTING
   do
      ceph tell osd.${OSD} injectargs -- --osd_max_scrubs=1
   done

   # disable other scrubs
   ceph osd unset nodeep-scrub
   ceph osd unset noscrub
done
