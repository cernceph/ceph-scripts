# !/bin/bash 
#
# Compute per image stats, called by rbdtop.sh
# usage: ./rbdtop <osd num> <image id>
#

echo -e "\033[1;41m\033[40m[`date '+%F %T'`:rbdtop:$2]\033[0m Showing usage of image $2 (osd.$1)"

# TODO: write
# Total write size
# Average write size +(min/max) +count
echo -e "\033[1;41m\033[40m[`date '+%F %T'`:rbdtop:$2]\033[0m Write ops summary"
cat /var/log/ceph/ceph-osd.$1.log | grep -E "$2"  | grep -oE "\[writefull [0-9]+~[0-9]+\]" | uniq -c | tr -d "][" | sed 's/~/ /'
cat /var/log/ceph/ceph-osd.$1.log | grep -E "$2"  | grep -oE "\[write [0-9]+~[0-9]+\]" | uniq -c | tr -d "][" | sed 's/~/ /'


# TODO: read
# Total read size
# Average read size +(min/max) +count
echo -e "\033[1;41m\033[40m[`date '+%F %T'`:rbdtop:$2]\033[0m Read ops summary"
cat /var/log/ceph/ceph-osd.$1.log | grep -E "$2"  | grep -oE "\[sparse-read [0-9]+~[0-9]+\]" | uniq -c | tr -d "][" | sed 's/~/ /'
cat /var/log/ceph/ceph-osd.$1.log | grep -E "$2"  | grep -oE "\[read [0-9]+~[0-9]+\]" | uniq -c | tr -d "][" | sed 's/~/ /'


