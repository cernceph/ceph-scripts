#! /bin/bash

INITSTATE=`ceph health`
FORCEMODE=0;
VERBOSE=0
BLUESTORE=0;

while [[ $# -gt 0 ]]
do
  key="$1"

  case "$key" in
    -f) 
    shift; 
    FORCEMODE=1;
    ;;

    -v)
    shift;
    VERBOSE=1;   
    ;; 

    --osd)
    OSD=$2
    shift;
    shift;
    ;;

    --dev)
    DEV=$2
    shift;
    shift;
    ;;

    *)
    shift;
    ;;
  esac
done

function draw(){
  if [[ $VERBOSE -eq 1 ]];
  then 
    echo ${1}
  fi
}

if [[ `echo $INITSTATE | grep -q "HEALTH_OK"` -eq 0 ]]; 
then
  if [[ $FORCEMODE -eq 0 ]];
  then
    echo "Ceph is unhealthy, aborting"
    exit
  else
    draw "Ceph is unhealthy"
  fi
else
  draw "Ceph is healthy"
fi


if [[ ! `ceph-disk list | grep -q LVM2` -eq 0 ]];
then
  draw "Bluestore OSDs on the host"
  BLUESTORE=1
fi

#IF osd is undefined
if [[ -z $OSD ]];
then
  draw "No osd provided"
  if [[ $BLUESTORE -eq 1 ]];
  then
    OSD=`lvs -o +devices,tags | grep "$DEV" | grep -E "type=block" | grep -Eo "osd_id=[0-9]+" | tr -d "[a-z=_]"`
  else
    OSD=`ceph-disk list | grep "^ $DEV" | grep -oE "osd\.[0-9]+" | tr -d "[osd\.]"`
  fi
fi
draw "$DEV is osd.$OSD"

if [[ `ceph osd safe-to-destroy osd.$OSD &> /dev/null` -eq 0 ]];
then
  echo "umount /var/lib/ceph/osd/ceph-$OSD"
  if [[ $BLUESTORE -eq 1 ]];
  then
    echo "ceph-volume lvm zap $DEV --destroy"
  else
    echo "ceph-volume lvm zap $DEV"
  fi
  #IF MOUNT/CEPH-DISK LIST/LVS say its ok
  #then
    echo "dd if=/dev/zero of=$DEV bs=1M"
    echo "smartctl -t long $DEV"
  #fi
else
  draw "OSD.$OSD not safe to destroy."
  draw "Exiting"
  exit;
fi

 
