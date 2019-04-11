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

echo $INITSTATE | grep -q "HEALTH_OK"
if [[ $? -eq 1 ]]; 
then
  if [[ $FORCEMODE -eq 0 ]];
  then
    echo "# Ceph is $INITSTATE, aborting"
    echo "# Use -f to force execution"
    exit
  else
    draw "Ceph is $INITSTATE"
  fi
fi



if [[ `ceph-disk list 2>/dev/null | grep -q LVM2` -eq 0 ]];
then
  draw "Bluestore OSDs on the host"
  BLUESTORE=1
fi

#IF osd is undefined
if [[ $BLUESTORE -eq 1 ]];
then
  OSD=`lvs -o +devices,tags | grep "$DEV" | grep -E "type=block" | grep -Eo "osd_id=[0-9]+" | tr -d "[a-z=_]"`
else
  OSD=`ceph-disk list 2>/dev/null | grep "^ $DEV" | grep -oE "osd\.[0-9]+" | tr -d "[osd\.]"`
fi

if [[ -z $OSD ]];
then
  draw "$DEV has no OSD mapped to it."
  exit;
fi 

draw "$DEV is osd.$OSD"

if [[ `systemctl is-active ceph-osd@1120 --quiet;` -eq 0 ]];
then
  draw "osd.$OSD is active"
  if [[ `ceph osd ok-to-stop osd.$OSD &> /dev/null` -eq 0 ]];
  then
    echo "ceph osd out osd.$OSD;"
  fi
else
  echo "# osd.$OSD is already out draining."
fi


 
