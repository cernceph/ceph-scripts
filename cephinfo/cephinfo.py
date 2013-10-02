#!/usr/bin/env python
#
# cephinfo.py
#
# Simple wrapper around the Ceph JSON dumps
#
# Author: Dan van der Ster (daniel.vanderster@cern.ch)
#

import commands, json, string, sys

def get_json():
  global mon_data
  global osd_data
  global pg_data

  mon_json = commands.getoutput('ceph mon dump --format=json 2>/dev/null')
  pg_json  = commands.getoutput('ceph pg  dump --format=json 2>/dev/null')
  osd_json = commands.getoutput('ceph osd dump --format=json 2>/dev/null')

  mon_data = json.loads(mon_json)
  osd_data = json.loads(osd_json)
  pg_data  = json.loads(pg_json)

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
  }
  for pg in get_pg_stats():
    state = pg["state"]
    slist = string.split(state, "+")
    for s in slist:
      if not s in state_stats:
        print >> sys.stderr, "PG %s has unknown state %s" % (pg["pgid"], s)
      else:
        state_stats[s] += 1
  return state_stats

def get_n_mons():
  return len(mon_data['mons'])

def get_n_mons_quorum():
  return len(mon_data['quorum'])

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
