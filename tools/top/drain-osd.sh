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

if [[ -z $DEV ]];
then
  draw "no drive"
  exit
fi

if [[ `echo $INITSTATE | grep -q "HEALTH_OK"` -eq 1 ]]; 
then
  if [[ $FORCEMODE -eq 0 ]];
  then
    echo "Ceph is $INITSTATE, aborting"
    exit
  else
    draw "Ceph is $INITSTATE"
  fi
fi


if [[ `ceph-disk list | grep -q LVM2` -eq 0 ]];
then
  draw "Bluestore OSDs on the host"
  BLUESTORE=1
fi

#IF osd is undefined
if [[ $BLUESTORE -eq 1 ]];
then
  draw "Bluestore OSD"
  OSD=`lvs -o +devices,tags | grep "$DEV" | grep -E "type=block" | grep -Eo "osd_id=[0-9]+" | tr -d "[a-z=_]"`
else
  draw "Filestore OSD"
  OSD=`ceph-disk list | grep "^ $DEV" | grep -oE "osd\.[0-9]+" | tr -d "[osd\.]"`
fi
draw "$DEV is osd.$OSD"

if [[ `ceph osd ok-to-stop osd.$OSD &> /dev/null` -eq 0 ]];
then
  echo "systemctl stop ceph-osd@$OSD;"
  echo "ceph osd out osd.$OSD;"
fi


 
