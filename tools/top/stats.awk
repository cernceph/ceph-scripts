#!/usr/bin/awk -f

# stats.awk
# compute stats using ceph rbd log files

# TODO
# min/avg/max <op> size

BEGIN {
  print ARGV[1]; 
  op=ARGV[1]; 
  ARGV[1]="";
}

{

}

END {
}
