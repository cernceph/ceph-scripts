#!/bin/bash
#
# Usage: ./extract_top_results.sh <path to files> [<output folder>]
#

if [ -z $2 ]
then 
  echo "No output folder provided. Default to /tmp/"
else
  echo "Output folder is $2"
  of=$2"/"
  if [ ! -d $2 ]
  then 
    mkdir $of
  fi
fi

for token in "write" "read" "sparse-read" "writefull";
do
  echo $token
  for img in `cat $1/* | ./extract_images.awk $token | sort | uniq -c | sort -k1gr | grep -Eo "rbd_data\.[0-9a-z]+"`;
  do
    echo $img
    for imginfile in `grep -E "$img" -R $1 -l`; 
    do
      timestamp=`echo -n $imginfile" " | grep -Eo "[0-9]{4}\-[0-9]{2}-[0-9]{2}-[0-2][0-9]:[0-5][0-9]:[0-5][0-9]" | tr -d "\n"`
      imagestats=`cat $imginfile | ./extract_images.awk $token 1 | grep $img | tr -d "\n"`
      if [ ! -z "$imagestats" ]
      then
        echo $timestamp" "$imagestats  >> $of/$img.$token.out;
      fi
    done
    # output to img.token.out
  done
  echo ""
done

#
# TODO: Consider removing rbd image id in output file as featured in the filename itself
#
