#!/usr/bin/awk -f

# extract_images.awk <arg>
# small awk filter that prints images that performed op <arg>
# arg =  [write|read|sparse-read|writefull]

BEGIN {
  token=ARGV[1]":"; 
  ARGV[1]="";
  out=0;
}

{
  if( out )
    if ( $0 ~ /rbdtop|^$/ )
      out = 0;
    else
    print $2
  
  if( $0 ~ token )
    out = 1;
}
