#!/usr/bin/awk -f

# logfilter.awk
# small awk filter that prints only data if within two given timestamps

BEGIN {
  print ARGV[1]; start=ARGV[1]; ARGV[1]=""; 
  print ARGV[2]; end=ARGV[2]; ARGV[2]="";
}

{
  timestamp=$1" "$2
  if(timestamp >= start && timestamp <= end) {
    print $0
  }
}
