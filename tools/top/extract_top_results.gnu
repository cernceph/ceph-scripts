set xdata time
set style data lines
set timefmt '%Y-%m-%d-%H:%M:%S'
set format x "%Y-%m-%d-%H:%M:%S"
set autoscale y
set xtics rotate by 45 right
plot "/tmp/reallife_testing/rbd_data.34c7f57f106752.sparse-read.out" using 1:2 with linespoints
