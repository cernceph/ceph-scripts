echo "This script will ERASE this host's osds from the cluster"
read -p "Are you sure you want to proceed? (y/n): " -r
case $REPLY in
  y ) echo "Starting osd removal operation.";;
  * ) echo "Exiting..."; exit 0;;
esac

if [[ $(pgrep ceph-osd | wc -l) == 0 ]]; then
	echo -e "No ceph-osd process running in this host.\nExiting..."
	exit 0
fi

echo "Killing all ceph-osd processes..."
kill $(pgrep ceph-osd)
sleep 5

OSD_LIST=$(ceph-volume lvm list | grep -oP "osd\\.\K[0-9]*")
R=1

for OSD in $OSD_LIST;
do
	if ! ceph osd purge $OSD --yes-i-really-mean-it; then
		R=0;
		break;
	fi
done

if [[ $R == 0 ]]; then
	echo "Error when trying to purge an osd from the cluster, exiting..."
	exit 0;
fi

PV_OUT=($(pvdisplay -c | grep ceph | awk -F ':' '{ gsub(/^ */, "", $1); print $1; print $2;}'))

for (( i=0; i<${#PV_OUT[@]} ; i+=2 ));
do
	PHYS=${PV_OUT[i]}
	VG=${PV_OUT[i+1]}

	lvremove -f $(pvdisplay -m $PHYS | grep -Po '/dev/ceph(-[0-9a-z]*)*/osd(-[0-9a-z]*)*' | cut -c 6-)
	vgremove $VG
	pvremove $PHYS
	ceph-volume lvm zap $PHYS
done
