# !/bin/bash 
#
#
# ./rbdtop.sh <osd> <time frame>
# <osd> the id of the osd under scrutiny
# <time_frame> logs gathering period

# activate appropriate debug level 
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Adjusting debug level to osd.$1"
ceph tell osd.$1 injectargs --debug_ms 1

# compute timeframe
start_window=`date '+%F %T'`
end_window=$(date -d "$start_window today + $2 second" +'%F %T');

# wait for a while
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Gathering logs for $2 secs"
sleep $2;

# gather some logs
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Logs collected, parsing"
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m logfile is: " `ls /var/log/ceph/ceph-osd.$1.log`
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m OSD operation summary ($start_window -> $end_window):"
sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$1.log | grep -Eo "\[[acrsw][a-z-]+" | sort -h | uniq -c | tr -d '['

# print time info
#sed -n '/2018-05-22 15:08:37/,/2018-05-22 15:08:41/p' /var/log/ceph/ceph-osd.$i.log | grep -Eo "^[0-9-]+ [0-9:]+" | uniq -c


# deactivate logging before exit
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Deactivate logging"
ceph tell osd.$1 injectargs --debug_ms 0
