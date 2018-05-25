#! /bin/bash
#
# usage: ./large_multi_image_rbd_bench.sh <bench count> <io-size> <threads> <io-total>
#
# <bench_count> number of bench to execute per image
# <io-size> 	size of io operations performed by rbd bench
# <threads>	thread count 
# <io-total>	total io size for rbd bench

for i in `seq 1 $1`; 
do
  for a in 00 01 02 10 11 12 20 21 22; 
  do
    if [ $((`od -An -N4 -t u4  < /dev/random` % 2)) -eq 1 ]; 
    then
      rbd bench --image jcollet-test-pool/test-image-$a$b --io-size $2 --io-threads $3 --io-total $4 --io-type read &
    else
      rbd bench --image jcollet-test-pool/test-image-$a$b --io-size $2 --io-threads $3 --io-total $4 --io-type write &
    fi; 
  done;
  wait;
done; 

