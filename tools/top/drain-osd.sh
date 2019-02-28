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


draw "Investigating OSD $OSD"
draw "Checking ceph health"
draw $INITSTATE


if [[ `echo $INITSTATE | grep -q "HEALTH_OK"` -eq 0 ]]; 
then
    if [[ $FORCEMODE -eq 0 ]];
    then
        draw "Ceph is unhealthy, aborting"
        exit
    else
        draw "Ceph is unhealthy"
    fi
else
    draw "Ceph is healthy"
fi


if [[ `ceph-disk list | grep -q LVM2` -eq 0 ]];
then
    draw "Bluestore OSDs on the host"
    BLUESTORE=1
fi

ceph-disk list | grep "$OSD"
lvs -o +devices,tags | grep "$OSD" | grep -oE "/dev/sd[a-z]?[a-z]"

