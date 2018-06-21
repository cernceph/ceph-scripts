# !/bin/bash 
#
# Print rbd image usage on current osd
# usage: ./rbdtop.sh <osd> <time frame>
# <osd> the id of the osd under scrutiny
# <time_frame> logs gathering period


usage="rbdtop.sh 

where:
    -h show this help text
    -o <id>: the id of the osd under scrutiny  (defaul: all osds)
    -l <length> logs gathering period (default: 30s)"

full_osd=0
len=30

while getopts 'ho:l:' opt; do
  case "$opt" in
    h) echo "$usage"
       exit
       ;;
    o) osd_id=$OPTARG
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

start=`date '+%F %T'`;
end=`date -d "$start today + 30 second" +'%F %T'`;

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

# collect logs
if [ $full_osd -eq 0 ];
then
  if [ "$end_ws" -ge "$now_ws" ];
  then  
    # activate appropriate debug level 
    echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Adjusting debug level to osd.$osd_id"
    ceph tell osd.$osd_id injectargs --debug_ms 1
  
    echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Gathering logs for $len secs"
    sleep $len;
  
    # deactivate logging before exit
    echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Deactivate logging"
    ceph tell osd.$osd_id injectargs --debug_ms 0
  
  else  # read old logs
    echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Collecting $len secs of logs"
  fi

  # gather some logs
  active_image_count=`cat /var/log/ceph/ceph-osd.$osd_id.log | grep -E "\[[acrsw][a-z-]+" | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | wc -l`;
  
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Logs collected, parsing"
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m logfile is: " `ls /var/log/ceph/ceph-osd.$osd_id.log`
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m OSD operation summary ($active_image_count active images):"
  grep -Eo "\[[wacrs][rep][a-z-]+" /var/log/ceph/ceph-osd.$osd_id.log | sort -h | uniq -c | tr -d '['
  
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Image statistics:"
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - write: "
  grep -E "\[write " /var/log/ceph/ceph-osd.$osd_id.log | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5 
  
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - writefull: "
  grep -E "\[writefull" /var/log/ceph/ceph-osd.$osd_id.log | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5
  
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - read: "
  grep -E "\[read" /var/log/ceph/ceph-osd.$osd_id.log | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5
  
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - sparse-read: "
  grep -E "\[sparse-read" /var/log/ceph/ceph-osd.$osd_id.log | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5

else
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Adjusting debug level to all osds"
  for f in `ls /var/run/ceph/ceph-osd.*.asok | tr -d '[a-zA-Z/\.\-]'`; 
  do
    touch /var/log/ceph/ceph-osd."$f".log 
    echo -n $f" ";
    ceph tell osd.$f injectargs --debug_ms 1
  done


  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Gathering logs for $len secs"
  sleep $len;

  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Deactivate logging"
  for f in `ls /var/run/ceph/ceph-osd.*.asok | tr -d '[a-zA-Z/\.\-]'`; 
  do
    ceph tell osd.$f injectargs --debug_ms 0
  done
  
  # extract files
  mkdir /tmp/rbdtop/ 
  for id in `ls /var/run/ceph/ceph-osd.*.asok | tr -d '[a-zA-Z/\.\-]'`; 
  do
    ./logfilter.awk "$start" "$end" /var/log/ceph/ceph-osd.$id.log > /tmp/rbdtop/ceph-osd.$id.log
  done
  
  # gather some logs
  active_image_count=`cat /tmp/rbdtop/ceph-osd.[0-9]*.log | grep -E "\[[acrsw][a-z-]+" | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | wc -l`;
  
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Logs collected, parsing"
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m logfile is /tmp/rbdtop/ceph-osd.[0-9]*.log"
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m OSD operation summary ($active_image_count active images):"
  grep -Eo "\[write " /tmp/rbdtop/ceph-osd.[0-9]*.log | sort -h | uniq -c | tr -d '[' | sed 's/:/ /' | sort -k1gr | head -n 5
  grep -Eo "\[writefull" /tmp/rbdtop/ceph-osd.[0-9]*.log | sort -h | uniq -c | tr -d '[' | sed 's/:/ /' | sort -k1gr | head -n 5
  grep -Eo "\[read" /tmp/rbdtop/ceph-osd.[0-9]*.log | sort -h | uniq -c | tr -d '[' | sed 's/:/ /' | sort -k1gr | head -n 5
  grep -Eo "\[sparse-read" /tmp/rbdtop/ceph-osd.[0-9]*.log | sort -h | uniq -c | tr -d '[' | sed 's/:/ /' | sort -k1gr | head -n 5
  
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m Image statistics:"
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - write: "
  grep -E "\[write " /tmp/rbdtop/ceph-osd.[0-9]*.log | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5 
  
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - writefull: "
  grep -E "\[writefull" /tmp/rbdtop/ceph-osd.[0-9]*.log | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5
  
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - read: "
  grep -E "\[read" /tmp/rbdtop/ceph-osd.[0-9]*.log | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5
  
  echo -e "\033[1;31m\033[40m[`date '+%F %T'`/rbdtop]\033[0m   - sparse-read: "
  grep -E "\[sparse-read" /tmp/rbdtop/ceph-osd.[0-9]*.log | grep -Eo "rbd_data\.[0-9a-f]+" | sort -h | uniq -c | sort -k1gr | head -n 5
fi

#cleanup
#rm -rf /tmp/rbdtop/


#TODO:
#
# replace grep in the analysis by awk scripts or lexer ?
 
