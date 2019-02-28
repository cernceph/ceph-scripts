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

#IF osd is undefined
OSD=`lvs -o +devices,tags | grep "$DEV" | grep -E "type=block" | grep -Eo "osd_id=[0-9]+" | tr -d "[a-z=_]"`
draw "$DEV is osd.$OSD"

if [[ `ceph osd ok-to-stop osd.$OSD &> /dev/null` -eq 0 ]];
then
    echo "ceph ok-to-stop osd.$OSD;"
    echo "systemctl stop ceph.$OSD;"
    echo "ceph osd out osd.$OSD;"
fi


 
