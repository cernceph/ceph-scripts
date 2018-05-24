# !/bin/bash 
#
#
# ./rbdtop.sh <osd> <time frame>
# <osd> the id of the osd under scrutiny
# <time_frame> logs gathering period
# <start_window> starting point of log analysis window (opt.)

# activate appropriate debug level 
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Adjusting debug level to osd.$1"
ceph tell osd.$1 injectargs --debug_ms 1

# compute timeframe
echo $3 | grep -Eo "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" > /dev/null;
if [ $? -eq 0 ];
then 
	start_window=`echo $3 | grep -Eo "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}"`;
else
	if [ ! -z "$3" ];
	then 
		echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Argument 3 mispelled - using current time as time window start"
		echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m (format expected: 'YYYY-MM-DD HH:MM:SS')"
	fi
	start_window=`date '+%F %T'`;
fi

end_window=$(date -d "$start_window today + $2 second" +'%F %T');

# collect logs
end_ws=`date -d "$end_window" "+%s"`
now_ws=`date "+%s"`
delta=$(($end_ws - $now_ws))

if [ "$end_ws" -ge "$now_ws" ];
then	#future adjust sleep? 
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Gathering logs for $delta secs"
	sleep $2;
else	#past 
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Collecting $2 secs of logs"
fi

# gather some logs
active_image_count=`sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$1.log | grep -E "\[[acrsw][a-z-]+" | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | wc -l`;

echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Logs collected, parsing"
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m logfile is: " `ls /var/log/ceph/ceph-osd.$1.log`
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Timeframe is: $start_window -> $end_window"
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m OSD operation summary ($active_image_count active images):"
sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$1.log | grep -Eo "\[[wacrs][rep][a-z-]+" | sort -h | uniq -c | tr -d '['

# TODO: print top5 busiest images
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Image statistics:"
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m   - write: "
sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$1.log | grep -E "\[write " | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c

echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m   - writefull: "
sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$1.log | grep -E "\[writefull" | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c

echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m   - read: "
sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$1.log | grep -E "\[read" | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c

echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m   - sparse-read: "
sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$1.log | grep -E "\[sparse-read" | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c

# deactivate logging before exit
echo -e "\033[1;31m\033[40m[`date '+%F %T'`:rbdtop]\033[0m Deactivate logging"
ceph tell osd.$1 injectargs --debug_ms 0
