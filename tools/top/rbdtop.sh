# !/bin/bash 
#
# Print rbd image usage on current osd
# usage: ./rbdtop.sh <osd> <time frame>
# <osd> the id of the osd under scrutiny
# <time_frame> logs gathering period
# <start_window> starting point of log analysis window (opt.)


usage="rbdtop.sh 

where:
    -h show this help text
    -o <id>: the id of the osd under scrutiny  (defaul: all osds)
    -l <timeframe> logs gathering period (default: 30s)
    -t <start_windows> starting point of log analysis"

full_osd=0
arg_timeframe=""
len=30

while getopts 'ho:l:t:' opt; do
  case "$opt" in
    h) echo "$usage"
       exit
       ;;
    o) osd_id=$OPTARG
       ;;
    t) arg_timeframe=$OPTARG
       ;;
    l) len=$OPTARG
       ;;
    :) printf "missing argument for -%s\n" "$OPTARG" >&2
       echo "$usage" >&2
       exit 1
       ;;
   \?) printf "illegal option: -%s\n" "$OPTARG" >&2
       echo "$usage" >&2
       exit 1
       ;;
  esac
done
shift $((OPTIND - 1))


# generate OSD list for the current machine
if [ -z "$osd_id" ];
then
 echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Going full osd mode"
 echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Generate list of OSDs in `hostname -s`"
 host=`hostname -s`;
 ceph osd tree | awk -v HN=$host 'BEGIN{toggle=0}  { if( $0 ~ HN ) {toggle=1}; if(toggle) { if( ($0 ~ /host/ || $0 ~ /rack/) && !($0 ~ HN)) {toggle=0} else { print $0; }}}' | grep -E "^[0-9]+"
 full_osd=1; 
 osd_id=0;
fi

# compute timeframe
echo $arg_timeframe | grep -Eo "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" > /dev/null;
if [ $? -eq 0 ];
then 
	start_window=`echo $arg_timeframe | grep -Eo "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}"`;
else
	if [ ! -z "$arg_timeframe" ];
	then 
		echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Argument 3 mispelled - using current time as time window start"
		echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m (format expected: 'YYYY-MM-DD HH:MM:SS')"
	fi
	start_window=`date '+%F %T'`;
fi

#
# TODO: Improve filtering using sed as it may not work everytime
#
end_window=$(date -d "$start_window today + $len second" +'%F %T');

# collect logs
end_ws=`date -d "$end_window" "+%s"`
now_ws=`date "+%s"`
delta=$(($end_ws - $now_ws))

if [ $full_osd -eq 0 ];
then
	if [ "$end_ws" -ge "$now_ws" ];
	then	
		# activate appropriate debug level 
		echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Adjusting debug level to osd.$osd_id"
		ceph tell osd.$osd_id injectargs --debug_ms 1
	
		echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Gathering logs for $delta secs"
		sleep $delta;
	
		# deactivate logging before exit
		echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Deactivate logging"
		ceph tell osd.$osd_id injectargs --debug_ms 0
	
	else	# read old logs
		echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Collecting $len secs of logs"
	fi

	# gather some logs
	active_image_count=`sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$osd_id.log | grep -E "\[[acrsw][a-z-]+" | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | wc -l`;
	
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Logs collected, parsing"
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m logfile is: " `ls /var/log/ceph/ceph-osd.$osd_id.log`
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Timeframe is: $start_window -> $end_window"
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m OSD operation summary ($active_image_count active images):"
	sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$osd_id.log | grep -Eo "\[[wacrs][rep][a-z-]+" | sort -h | uniq -c | tr -d '['
	
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Image statistics:"
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - write: "
	sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$osd_id.log | grep -E "\[write " | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5 
	
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - writefull: "
	sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$osd_id.log | grep -E "\[writefull" | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5
	
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - read: "
	sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$osd_id.log | grep -E "\[read" | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5
	
	echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - sparse-read: "
	sed -n "/$start_window/,/$end_window/p" /var/log/ceph/ceph-osd.$osd_id.log | grep -E "\[sparse-read" | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5

else
	echo "TBC"
fi



