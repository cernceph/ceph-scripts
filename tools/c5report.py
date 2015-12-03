#!/usr/bin/env python
# prints a daily report, format:
# 05/02/2014 space 192037936693248 size 39918660100096 files 207894707

from datetime import date
from cephinfo import cephinfo

cephinfo.init_df()

REPORTED = ('castor','dpm','images','volumes','atlassfst','.rgw.buckets')
REPORTED = ()

t_objects = 0
t_bytes_used = 0
for pool in cephinfo.df_data['pools']:
  if pool['name'] in REPORTED:
    print pool['name'],pool['stats']['objects'],pool['stats']['bytes_used']
  t_objects += pool['stats']['objects']
  t_bytes_used += pool['stats']['bytes_used']

print date.today().strftime("%d/%m/%Y"), 'totalbytes', cephinfo.df_data['stats']['total_bytes'], 'totalbytesused', t_bytes_used, 'totalobjects', t_objects
