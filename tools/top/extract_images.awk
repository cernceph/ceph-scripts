#!/usr/bin/awk -f

# extract_images.awk <arg> [<fullout>]
# small awk filter that prints images that performed op <arg>
# arg: operation to be watched, can be [write|read|sparse-read|writefull]
# fullout: optional flag. displays number of $arg operation per image when set

BEGIN {
  token=" "ARGV[1]":"; ARGV[1]="";
  fullout=ARGV[2]; ARGV[2]="";
  out=0;
}

{
  if( out )
    if ( $0 ~ /rbdtop|^$/ )
    {
      out = 0;
    }
    else
    {
      if(fullout != "") { print $0 }
      else              { print $2 }
    }

  if( $0 ~ token )
    out = 1;
}
