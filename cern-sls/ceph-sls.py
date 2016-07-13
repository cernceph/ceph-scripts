#!/usr/bin/env python
#
# ceph-sls.py
#
# Produce an XML file reporting the service level status of Ceph
#
# Author: Dan van der Ster (daniel.vanderster@cern.ch)
#

try: import simplejson as json
except ImportError: import json

import argparse
import commands
import cephinfo
import urllib2
import math
import sys
import time
import socket
from datetime import datetime
import math

CARBON_SERVER = 'filer-carbon.cern.ch'
CARBON_PORT = 2003


def get_status(pg_stats_sum, latency_ms):
  health = commands.getoutput('timeout 10 ceph health')

  if health.startswith('HEALTH_ERR'):
    return ('unavailable', health)

  if health == 'HEALTH_OK':
    return ('available', health)

  if pg_stats_sum['num_objects'] > 1 and pg_stats_sum['num_objects_degraded'] / pg_stats_sum['num_objects'] > 0.01:
    return ('degraded', health)

  if latency_ms > 100:
    return ('degraded', health)

  return ('available', health)


def write_xml(slsid='Ceph'):
  osd_states = cephinfo.get_osd_states()
  osd_stats_sum = cephinfo.get_osd_stats_sum()
  pg_stats_sum = cephinfo.get_pg_stats_sum()['stat_sum']
  pg_map = cephinfo.stat_data['pgmap']
  try:
    latency = cephinfo.get_write_latency()
    read_latency = cephinfo.get_read_latency()
    cephinfo.rados_cleanup(latency[0])
  except IndexError:
    latency = ['',[0,0,0]]
    read_latency = [0,0,0]
  pg_states = cephinfo.get_pg_states()
  osd_df = cephinfo.osd_df_data['nodes']
  activity = cephinfo.get_smooth_activity(10)
  status, availabilityinfo = get_status(pg_stats_sum, latency[1][0]*1000)
  context = {
    "slsid"              : slsid,
    "timestamp"          : datetime.strftime(datetime.now(), '%Y-%m-%dT%H:%M:%S'),
    "status"             : status,
    "availabilityinfo"   : availabilityinfo,
    "n_mons"             : cephinfo.get_n_mons(),
    "n_quorum"           : cephinfo.get_n_mons_quorum(),
    "n_pools"            : cephinfo.get_n_pools(),
    "n_osds"             : cephinfo.get_n_osds(),
    "n_osds_up"          : osd_states['up'],
    "n_osds_in"          : osd_states['in'],
    "n_pgs"              : cephinfo.get_n_pgs(),
    "n_osd_gb_total"     : osd_stats_sum['kb'] / 1024 / 1024,
    "n_osd_gb_used"      : osd_stats_sum['kb_used'] / 1024 / 1024,
    "n_osd_gb_avail"     : osd_stats_sum['kb_avail'] / 1024 / 1024,
    "n_pg_gbytes"        : pg_stats_sum['num_bytes'] / 1024 / 1024 / 1024,
    "n_objects"          : pg_stats_sum['num_objects'],
    "n_object_copies"    : pg_stats_sum['num_object_copies'],
    "n_objects_degraded" : pg_stats_sum['num_objects_degraded'],
    "n_objects_unfound"  : pg_stats_sum['num_objects_unfound'],
    "n_objects_misplaced": pg_stats_sum['num_objects_misplaced'],
    "n_read_gb"          : pg_stats_sum['num_read_kb'] / 1024 / 1024,
    "n_write_gb"         : pg_stats_sum['num_write_kb'] / 1024 / 1024,
    "latency_ms"         : latency[1][0]*1000,
    "latency_max_ms"     : latency[1][1]*1000,
    "latency_min_ms"     : latency[1][2]*1000,
    "read_latency_ms"    : read_latency[0]*1000,
    "read_latency_max_ms": read_latency[1]*1000,
    "read_latency_min_ms": read_latency[2]*1000,
    "n_openstack_volumes": cephinfo.get_n_openstack_volumes(),
    "n_openstack_images" : cephinfo.get_n_openstack_images(),
    "op_per_sec"         : activity[0],
    "read_mb_sec"        : activity[1],
    "write_mb_sec"       : activity[2],
    "graphite_prefix"    : slsid.replace('_','.').lower() + '.sls',
    "graphite_osd_prefix": slsid.replace('_','.').lower() + '.osds',
    "graphite_timestamp" : int(time.time()),
  }

  for state in pg_states.keys():
    context['n_pgs_%s' % state] = pg_states[state]

  template = """
<?xml version="1.0" encoding="utf-8"?>

<serviceupdate xmlns="http://sls.cern.ch/SLS/XML/update">
    <id>{slsid}</id>

    <contact>ceph.support@cern.ch</contact>
    <webpage>https://twiki.cern.ch/twiki/bin/viewauth/DSSGroup/CephProject</webpage>

    <availabilitydesc>Status is available, degraded, or unavailable when the Ceph status is HEALTH_OK, HEALTH_WARN, or HEALTH_ERR, respectively.</availabilitydesc>

    <timestamp>{timestamp}</timestamp>

    <status>{status}</status>

    <availabilityinfo>{availabilityinfo}</availabilityinfo>

    <data>
        <numericvalue name="n_mons" desc="Num Mons">{n_mons}</numericvalue>
        <numericvalue name="n_quorum" desc="Num Mons in Quorum">{n_quorum}</numericvalue>
        <numericvalue name="n_pools" desc="Num Pools">{n_pools}</numericvalue>
        <numericvalue name="n_osds" desc="Num OSDs">{n_osds}</numericvalue>
        <numericvalue name="n_osds_up" desc="Num OSDs Up">{n_osds_up}</numericvalue>
        <numericvalue name="n_osds_in" desc="Num OSDs In">{n_osds_in}</numericvalue>
        <numericvalue name="n_pgs" desc="Num PGs">{n_pgs}</numericvalue>
"""

  for state in pg_states.keys():
    template = template + '        <numericvalue name="n_pgs_%s" desc="Num PGs %s">{n_pgs_%s}</numericvalue>\n' % (state, state, state)

  template = template + """        <numericvalue name="n_osd_gb_total" desc="OSD Gigabytes Total">{n_osd_gb_total}</numericvalue>
        <numericvalue name="n_osd_gb_used" desc="OSD Gigabytes Used">{n_osd_gb_used}</numericvalue>
        <numericvalue name="n_osd_gb_avail" desc="OSD Gigabytes Avail">{n_osd_gb_avail}</numericvalue>
        <numericvalue name="n_pg_gbytes" desc="PG Gigabytes">{n_pg_gbytes}</numericvalue>
        <numericvalue name="n_objects" desc="Num Objects">{n_objects}</numericvalue>
        <numericvalue name="n_object_copies" desc="Num Object Copies">{n_object_copies}</numericvalue>
        <numericvalue name="n_objects_degraded" desc="Num Objects Degraded">{n_objects_degraded}</numericvalue>
        <numericvalue name="n_objects_unfound" desc="Num Objects Unfound">{n_objects_unfound}</numericvalue>
        <numericvalue name="n_objects_misplaced" desc="Num Objects Misplaced">{n_objects_misplaced}</numericvalue>
        <numericvalue name="n_read_gb" desc="Total Read (GB)">{n_read_gb}</numericvalue>
        <numericvalue name="n_write_gb" desc="Total Write (GB)">{n_write_gb}</numericvalue>
        <numericvalue name="latency_ms" desc="Average">{latency_ms}</numericvalue>
        <numericvalue name="latency_max_ms" desc="Max">{latency_max_ms}</numericvalue>
        <numericvalue name="latency_min_ms" desc="Min">{latency_min_ms}</numericvalue>
        <numericvalue name="read_latency_ms" desc="Average">{read_latency_ms}</numericvalue>
        <numericvalue name="read_latency_max_ms" desc="Max">{read_latency_max_ms}</numericvalue>
        <numericvalue name="read_latency_min_ms" desc="Min">{read_latency_min_ms}</numericvalue>
        <numericvalue name="n_openstack_volumes" desc="Num OpenStack Volumes">{n_openstack_volumes}</numericvalue>
        <numericvalue name="n_openstack_images" desc="Num OpenStack Images">{n_openstack_images}</numericvalue>
        <numericvalue name="read_mb_sec" desc="Read MB/s">{read_mb_sec}</numericvalue>
        <numericvalue name="write_mb_sec" desc="Write MB/s">{write_mb_sec}</numericvalue>
        <numericvalue name="op_per_sec" desc="Operations Per Second">{op_per_sec}</numericvalue>
    </data>
</serviceupdate>
"""
  print template.format(**context)

  # generate Graphite update
  graphite = """
{graphite_prefix}.n_mons {n_mons} {graphite_timestamp}
{graphite_prefix}.n_quorum {n_quorum} {graphite_timestamp}
{graphite_prefix}.n_pools {n_pools} {graphite_timestamp}
{graphite_prefix}.n_osds {n_osds} {graphite_timestamp}
{graphite_prefix}.n_osds_up {n_osds_up} {graphite_timestamp}
{graphite_prefix}.n_osds_in {n_osds_in} {graphite_timestamp}
{graphite_prefix}.n_pgs {n_pgs} {graphite_timestamp}
"""

  for state in pg_states.keys():
    graphite = graphite + "{graphite_prefix}.n_pgs_%s {n_pgs_%s} {graphite_timestamp}\n" % (state, state)

  graphite = graphite + """{graphite_prefix}.n_osd_gb_total {n_osd_gb_total} {graphite_timestamp}
{graphite_prefix}.n_osd_gb_used {n_osd_gb_used} {graphite_timestamp}
{graphite_prefix}.n_osd_gb_avail {n_osd_gb_avail} {graphite_timestamp}
{graphite_prefix}.n_pg_gbytes {n_pg_gbytes} {graphite_timestamp}
{graphite_prefix}.n_objects {n_objects} {graphite_timestamp}
{graphite_prefix}.n_object_copies {n_object_copies} {graphite_timestamp}
{graphite_prefix}.n_objects_degraded {n_objects_degraded} {graphite_timestamp}
{graphite_prefix}.n_objects_unfound {n_objects_unfound} {graphite_timestamp}
{graphite_prefix}.n_objects_misplaced {n_objects_misplaced} {graphite_timestamp}
{graphite_prefix}.n_read_gb {n_read_gb} {graphite_timestamp}
{graphite_prefix}.n_write_gb {n_write_gb} {graphite_timestamp}
{graphite_prefix}.latency_ms {latency_ms} {graphite_timestamp}
{graphite_prefix}.latency_max_ms {latency_max_ms} {graphite_timestamp}
{graphite_prefix}.latency_min_ms {latency_min_ms} {graphite_timestamp}
{graphite_prefix}.read_latency_ms {read_latency_ms} {graphite_timestamp}
{graphite_prefix}.read_latency_max_ms {read_latency_max_ms} {graphite_timestamp}
{graphite_prefix}.read_latency_min_ms {read_latency_min_ms} {graphite_timestamp}
{graphite_prefix}.n_openstack_volumes {n_openstack_volumes} {graphite_timestamp}
{graphite_prefix}.n_openstack_images {n_openstack_images} {graphite_timestamp}
{graphite_prefix}.read_mb_sec {read_mb_sec} {graphite_timestamp}
{graphite_prefix}.write_mb_sec {write_mb_sec} {graphite_timestamp}
{graphite_prefix}.op_per_sec {op_per_sec} {graphite_timestamp}
"""

  for osd in osd_df:
    graphite = graphite + "{graphite_osd_prefix}.%s.crush_weight %s {graphite_timestamp}\n" % (osd['id'], osd['crush_weight'])
    graphite = graphite + "{graphite_osd_prefix}.%s.reweight %s {graphite_timestamp}\n" % (osd['id'], osd['reweight'])
    graphite = graphite + "{graphite_osd_prefix}.%s.kb %s {graphite_timestamp}\n" % (osd['id'], osd['kb'])
    graphite = graphite + "{graphite_osd_prefix}.%s.kb_used %s {graphite_timestamp}\n" % (osd['id'], osd['kb_used'])
    graphite = graphite + "{graphite_osd_prefix}.%s.kb_avail %s {graphite_timestamp}\n" % (osd['id'], osd['kb_avail'])
    graphite = graphite + "{graphite_osd_prefix}.%s.utilization %s {graphite_timestamp}\n" % (osd['id'], osd['utilization'])
    graphite = graphite + "{graphite_osd_prefix}.%s.var %s {graphite_timestamp}\n" % (osd['id'], osd['var'])

  update = graphite.format(**context)
  sock = socket.socket()
  sock.connect((CARBON_SERVER, CARBON_PORT))
  sock.sendall(update)
  sock.close()

# main

parser = argparse.ArgumentParser(description="CERN Ceph SLS Probe")
parser.add_argument('-i', '--id', help='SLS ID, e.g. Ceph, Ceph_Preprod, Ceph_Wigner')

parsed_args, rest = parser.parse_known_args()

cephinfo.get_json()
write_xml(parsed_args.id)
