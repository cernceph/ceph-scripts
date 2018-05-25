#! /bin/bash
#
# usage: ./custom_rbd_bench.sh <bench count> <io-size> <threads> <io-total>
#
# <bench_count> number of bench to execute
# <io-size> 	size of io operations performed by rbd bench
# <threads>	thread count 
# <io-total>	total io size for rbd bench

for id in 00 11; 
do
  for i in `seq 1 $1`; 
  do
    rbd bench --image jcollet-test-pool/test-image-$id --io-size $2 --io-threads $3 --io-total $4 --io-type read
    rbd bench --image jcollet-test-pool/test-image-$id --io-size $2 --io-threads $3 --io-total $4 --io-type write
  done;
done; 
