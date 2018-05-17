# !/bin/bash 
#
#
# ./rbdtop.sh <osd> <time frame>
# <osd> the id of the osd under scrutiny
# <time_frame> log gathering period

RBDTOP='\033[1;31m\033[40m[rbdtop]\033[0m'


# activate appropriate debug level 
echo -e "${RBDTOP} Adjusting debug level to osd.$1"
ceph tell osd.$1 injectargs --debug_ms 1

# wait for a while
echo -e "${RBDTOP} Gathering log for $2 secs"
sleep $2;

# gather some logs
echo -e "${RBDTOP} Logs collected, parsing."
echo -e "${RBDTOP} logfile is: " `ls /var/log/ceph/ceph-osd.$1.log`

echo -e "${RBDTOP} OSD operation summary:"
cat /var/log/ceph/ceph-osd.55.log | grep -Eo "\[[acrsw][a-z-]+" | sort -h | uniq -c | tr -d '['


# deactivate logging before exit
ceph tell osd.$1 injectargs --debug_ms 0
