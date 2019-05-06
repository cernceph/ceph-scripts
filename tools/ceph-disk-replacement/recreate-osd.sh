#! /bin/bash

if [[ `cat /etc/motd | grep hostgroup | grep -Eo "ceph/[a-Z0-9/]+" | grep -c castor` -eq 1 ]];
then
  echo "echo \"Castor nodes need special handling: contact ceph-admins\""
  exit
fi


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

        --db)
        DBD=$2  
        shift;
        shift;
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

if [[ -z $DEV ]];
then
  echo "echo \"No drive passed\""
  exit
fi

if [[ `echo $DEV | grep -Eo "/dev/sd[a-z][a-z]?" -c` -eq 0 ]];
then
  echo "echo \"Argument malformed, check spelling\""
  exit
fi

echo $INITSTATE | grep -q "HEALTH_OK"
if [[ $? -eq 1 ]]; 
then
  if [[ $FORCEMODE -eq 0 ]];
  then
    echo "echo \"Ceph is $INITSTATE, aborting\""
    echo "echo \"Use -f to force execution\""
    exit
  else
    draw "# Ceph is $INITSTATE"
  fi
fi


if [[ -z $OSD ]];
then
    AWKHOST=`echo $HOSTNAME | sed 's/.cern.ch//'`
    OSD=`ceph osd tree down | awk -v awkhost=$AWKHOST 'BEGIN { out=0 } { if($0 ~ /rack/) {out=0} if(out) {print $0; out=0} if($0 ~ awkhost) {out=1}; }' | grep -Eo "osd\.[0-9]+" | tr -d "[a-z\.]"`
fi

if [[ -z $OSD ]];
then
    echo "echo \"No down OSD found on this host. Contact ceph-admins.\""
    exit
fi

if [[ -z $DBD ]];
then 
  for i in `ceph-disk list 2>/dev/null | grep -E "ceph journal"  | grep -vE "for" | grep -oE "/dev/sd[a-z]+[0-9]"`;
  do 
    draw "investigating $i"
    lvs -o +devices,tags | grep -q $i; 
    if [[ $? -eq 1 ]];
    then 
      draw "$i can be used";
      DBD=$i;
    fi;
  done
  if [[ -z $DBD ]];
  then
    draw "No block device found, switching to ceph-volume"
    DBD=`ceph-volume lvm list | awk -v awkosdid=osd.$OSD 'BEGIN { out=0 } { if($0 ~ /====/) {out=0} if(out) {print $0;} if($0 ~ awkosdid) {out=1}; }'  | grep -Eo "db device.*$" | sed 's/db device.*\/dev\///';`
  fi
fi


echo "ceph-volume lvm zap $DEV"


if [[ -z $DBD ]];
then 
  echo "ceph osd destroy $OSD --yes-i-really-mean-it"
  echo "ceph-volume lvm create --osd-id $OSD --data $DEV"
else
  echo "ceph-volume lvm zap $DBD"
  echo "ceph osd destroy $OSD --yes-i-really-mean-it"
  echo "ceph-volume lvm create --osd-id $OSD --data $DEV --block.db $DBD"
fi


## TODO
#
# Auto discover osd to be replaced (grep on ceph osd tree down to find down osd on the host)
# Auto find if 2-disk OSDs are used

 
#  awk 'BEGIN { out=0 } { if($0 ~ /rack/) {out=0} if(out) {print $0} if($0 ~ /RJ55/) {out=1}; } '
