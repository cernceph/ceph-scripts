#!/usr/bin/perl -w
#
# rbd-io-stats.pl
#
# Gather some IO statistics about RBD volumes from the gzipped OSD logs.
#
# The OSD logs must contain the filestore messages at log level 10. Enable 
# that dynamically with something like
#
#    ceph tell osd.0 injectargs '--debug_filestore 10'
#
# or
#
#    ceph tell osd.* injectargs '--debug_filestore 10'
#
# or via ceph.conf on the OSDs:
#
# [osd]
#        debug filestore = 10
#
# Usage: 
#
#   rbd-io-stats.pl logfile.gz [logfile2.gz ...]
#
# Example usage:
#
#   ./rbd-io-stats.pl /var/log/ceph/ceph-osd.0.log-20140416.gz
#   ./rbd-io-stats.pl /var/log/ceph/ceph-osd.*.log-20140416.gz
#  

use strict;

my %w_osds;
my %w_pools;
my %w_pgs;
my %w_objects;
my %w_rbds;
my %w_lengths;

my %r_osds;
my %r_pools;
my %r_pgs;
my %r_objects;
my %r_rbds;
my %r_lengths;

die "Usage: $0 logfile.gz [logfile2.gz ...]\n" if (scalar @ARGV < 1);

foreach my $log_file (@ARGV) {

  open (IN, "zcat -f $log_file |");

  while (<IN>) {

    if (/10 filestore\(\/var\/lib\/ceph\/osd\/ceph-(\d+)\) write (\S+) (\d+)~(\d+) = (\d+)/) {
#2014-04-14 03:14:03.924341 7fb39df16700 10 filestore(/var/lib/ceph/osd/osd.0) write 4.b1d_head/9ac3fb1d/rbd_data.eed4792ae8944a.0000000000003260/head//4 712704~503808 = 503808
#2014-08-11 12:43:25.477693 7f022d257700 10 filestore(/var/lib/ceph/osd/ceph-0) write 3.48_head/14b1ca48/rbd_data.41e16619f5eb6.0000000000001bd1/head//3 3641344~4608 = 4608
      my ($osd, $object, $start, $foo, $length) = ($1, $2, $3, $4, $5);
      $w_osds{$osd}++;
      $w_objects{$object}++;
      $w_lengths{$length}++;

      $object =~ m/^(\d+)\./;
      my $pool = $1;
      $w_pools{$pool}++;

      $object =~ m/^(.+)_.+\/.+\/rbd_data/;
      my $pg = $1;
      $w_pgs{$pg}++;

      $object =~ m/rbd_data\.(.+)\./;
      my $rbd = 'rbd_data.'.$1;
      $w_rbds{$rbd}++;
    } elsif (/10 filestore\(\/var\/lib\/ceph\/osd\/ceph-(\d+)\) FileStore::read (\S+) (\d+)~(\d+)\/(\d+)/) {
# 2014-04-14 03:14:22.622039 7fb392427700 10 filestore(/var/lib/ceph/osd/osd.0) FileStore::read 4.fe9_head/56091fe9/rbd_data.114cff265bee204.0000000000000e9a/head//4 40960~4096/4096
      my ($osd, $object, $start, $foo, $length) = ($1, $2, $3, $4, $5);
      $r_osds{$osd}++;
      $r_objects{$object}++;
      $r_lengths{$length}++;

      $object =~ m/^(\d+)\./;
      my $pool = $1;
      $r_pools{$pool}++;

      $object =~ m/^(.+)_.+\/.+\/rbd_data/;
      my $pg = $1;
      $r_pgs{$pg}++;
  
      $object =~ m/rbd_data\.(.+)\./;
      my $rbd = 'rbd_data.'.$1;
      $r_rbds{$rbd}++;
    }
  }

  close(IN);

}


sub pprint ($$) {
  my $message = shift;
  my $h = shift;

  print "$message\n";
  my $i = 0;
  foreach (sort {$h->{$b} <=> $h->{$a}} keys %{$h}) {
    print "$_: $h->{$_}\n";
    last if $i++ > 10;
  }
  print "\n";
}

pprint("Writes per OSD:",    \%w_osds);
pprint("Writes per pool:",   \%w_pools);
pprint("Writes per PG:",     \%w_pgs);
pprint("Writes per RBD:",    \%w_rbds);
pprint("Writes per object:", \%w_objects);
pprint("Writes per length:", \%w_lengths);

pprint("Reads per OSD:",    \%r_osds);
pprint("Reads per pool:",   \%r_pools);
pprint("Reads per PG:",     \%r_pgs);
pprint("Reads per RBD:",    \%r_rbds);
pprint("Reads per object:", \%r_objects);
pprint("Reads per length:", \%r_lengths);
