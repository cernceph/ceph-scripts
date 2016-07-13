#!/usr/bin/env python
#
# cephinfo.py
#
# Simple wrapper around the Ceph JSON dumps
#
# Author: Dan van der Ster (daniel.vanderster@cern.ch)
#

import commands, json, string, sys, time

def init_df():
  global df_data
  df_json = commands.getoutput('ceph df --format=json 2>/dev/null')
  df_data = json.loads(df_json)

def init_mon():
  global mon_data
  mon_json = commands.getoutput('ceph mon dump --format=json 2>/dev/null')
  mon_data = json.loads(mon_json)

def init_osd():
  global osd_data
  global osd_df_data
  osd_json = commands.getoutput('ceph osd dump --format=json 2>/dev/null')
  osd_data = json.loads(osd_json)
  osd_df_json = commands.getoutput('ceph osd df --format=json 2>/dev/null')
  osd_df_data = json.loads(osd_df_json)

def init_pg():
  global pg_data
  pg_json = commands.getoutput('ceph pg  dump --format=json 2>/dev/null')
  pg_data = json.loads(pg_json)

def init_auth():
  global auth_data
  auth_json = commands.getoutput('ceph auth list --format=json 2>/dev/null')
  auth_data = json.loads(auth_json)

def init_stat():
  global stat_data
  stat_json = commands.getoutput('ceph -s -f json 2>/dev/null')
  stat_data = json.loads(stat_json)

def init_crush():
  global crush_data
  crush_json = commands.getoutput('ceph osd tree -f json 2>/dev/null')
  crush_data = json.loads(crush_json)

def get_json():
  init_mon()
  init_osd()
  init_pg()
  init_auth()
  init_stat()

def get_pools_data():
  return list(osd_data['pools'])

def get_n_pools():
  return len(get_pools_data())

def get_osds_data():
  return list(osd_data['osds'])

def get_n_osds():
  return len(get_osds_data())

def get_osd_states():
  osd_states = {
    "up"   : 0,
    "down" : 0,
    "in"   : 0,
    "out"  : 0
  }
  for osd in get_osds_data():
    if osd['up'] == 1: osd_states['up']   += 1
    if osd['up'] == 0: osd_states['down'] += 1
    if osd['in'] == 1: osd_states['in']   += 1
    if osd['in'] == 0: osd_states['out']  += 1
  return osd_states

def get_pg_stats():
  return list(pg_data['pg_stats'])

def get_pg_stats_sum():
  return pg_data['pg_stats_sum']

def get_osd_stats_sum():
  return pg_data['osd_stats_sum']

def get_pg_stats_delta():
  return pg_data['pg_stats_delta']

def get_n_pgs():
  return len(get_pg_stats())

def get_pg_states():
  state_stats = {
    "active" : 0,
    "clean" : 0,
    "crashed" : 0,
    "creating" : 0,
    "degraded" : 0,
    "down" : 0,
    "stale" : 0,
    "inconsistent" : 0,
    "peering" : 0,
    "repair" : 0,
    "replay" : 0,
    "scanning" : 0,
    "scrubbing" : 0,
    "scrubq" : 0,
    "splitting" : 0,
    "stray" : 0,
    "inactive" : 0,
    "remapped" : 0,
    "deep" : 0,
    "backfilling" : 0,
    "recovering" : 0,
    "wait_backfill" : 0,
    "recovery_wait" : 0,
    "backfill_toofull" : 0,
    "incomplete" : 0,
    "undersized" : 0,
    "activating" : 0,
  }
  for pg in get_pg_stats():
    slist = string.split(pg["state"], "+")
    for s in slist:
      if s not in state_stats:
        state_stats[s] = 1
      else:
        state_stats[s] += 1
  return state_stats

def get_n_mons():
  return len(mon_data['mons'])

def get_n_mons_quorum():
  return len(mon_data['quorum'])

def get_write_latency():
  latency_ms = commands.getoutput('rados -p test bench 10 write -t 1 -b 4096 --no-cleanup 2>/dev/null | egrep -i \'latency|prefix\' | grep -vi stddev | awk \'{print $3}\'').split()
  return latency_ms[0],[float(x) for x in latency_ms[1:]]

def get_read_latency():
  latency_ms = commands.getoutput('rados -p test bench 10 rand -t 1 2>/dev/null | grep -i latency | awk \'{print $3}\'').split()
  return [float(x) for x in latency_ms]

def rados_cleanup(prefix):
  assert(prefix)
  commands.getoutput('rados -p test cleanup benchmark_data --prefix %s' % prefix)

def get_n_openstack_volumes():
  n = commands.getoutput('rbd ls -p volumes 2>/dev/null | wc -l')
  return int(n)

def get_n_openstack_images():
  n = commands.getoutput('rbd ls -p images 2>/dev/null | wc -l')
  return int(n)

def get_smooth_activity(n):
  sum_iops = 0
  sum_read = 0
  sum_write = 0
  count = 0
  for i in xrange(n):
    try:
      sum_iops += stat_data['pgmap']['op_per_sec']
    except KeyError:
      try:
        sum_iops += stat_data['pgmap']['read_op_per_sec'] + stat_data['pgmap']['write_op_per_sec']
      except KeyError:
        pass
    try:
      sum_read += stat_data['pgmap']['read_bytes_sec'] / 1024 / 1024
      sum_write += stat_data['pgmap']['write_bytes_sec'] / 1024 / 1024
      count += 1
    except KeyError:
      pass
    time.sleep(1)
    init_stat()
  try:
    return [int(sum_iops/count), int(sum_read/count), int(sum_write/count)]
  except ZeroDivisionError:
    return [0, 0, 0]

if __name__ == "__main__":
  # basic testing
  get_json()

  print "n pools:", get_n_pools()
  print "n osds:", get_n_osds()
  print "osd states", get_osd_states()
  print "n pgs:", get_n_pgs()
  print "pg states:", get_pg_states()
  print "n mons:", get_n_mons()
  print "n mons quorum:", get_n_mons_quorum()
