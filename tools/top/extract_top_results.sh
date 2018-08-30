#!/bin/bash
#
# Usage: ./extract_top_results.sh <path to files> [<output folder>] [<number of plots>]
#

if [ -z $2 ]
then 
  echo "No output folder provided. Default to /tmp/output/"
  mkdir /tmp/output
  of=/tmp/output/
else
  echo "Output folder is $2"
  of=$2"/"
  if [ ! -d $2 ]
  then 
    mkdir $of
  fi
fi

if [ -z $3 ]
then 
  echo "No tail arg provided, defaults to 10"
  tailnum=10;
else
  echo "Tail argument provided is: $3"
  tailnum=$3
fi

rm -f $of/rbd_data*

for token in "write" "read" "sparse-read" "writefull"; # Parallel loop here
do
  echo $token
  for img in `cat $1/* | ./extract_images.awk $token | sort | uniq -c | sort -k1gr | grep -Eo "rbd_data\.[0-9a-z]+"`;
  do
    echo $img
    for imginfile in `grep -E "$img" -R $1 -l | sort`; 
    do
      timestamp=`echo -n $imginfile" " | grep -Eo "[0-9]{4}\-[0-9]{2}-[0-9]{2}-[0-2][0-9]:[0-5][0-9]:[0-5][0-9]" | tr -d "\n"`
      imagestats=`cat $imginfile | ./extract_images.awk $token 1 | grep $img | tr -d "\n"`
      if [ ! -z "$imagestats" ]
      then
        echo $timestamp" "$imagestats  >> $of/$img.$token.out;
      fi
    done
    # output to img.token.out
  done &
  echo ""
done

wait

#
# GNUPLOT Script generation
#

cat prefix_gnuplot.template > $of/plot.gnu

echo plot \\ >> $of/plot.gnu ; 
cnt=0;
for i in `wc -l $of/* | grep -v total | sort -k1g | tr -d " " | sed 's/^[0-9]*//g' | tail -n $tailnum`; 
do
  echo \"$i\" using 1:2 w lp lt $cnt, \\ >> $of/plot.gnu;
  cnt=$((cnt+1));
done


#
# TODO: Consider removing rbd image id in output file as featured in the filename itself
# TODO: Consider parallelize
# TODO: Consider accounting for op sizes
#
