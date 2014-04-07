#!/usr/bin/env python

import commands
from cephinfo import cephinfo

cephinfo.init_auth()
cephinfo.init_osd()

yesno = 'n'

for entry in cephinfo.auth_data['auth_dump']:
  entity = entry['entity']
  if not entity.startswith('osd'):
    continue

  for osd in cephinfo.osd_data['osds']:
    if "osd.%d" % osd['osd'] == entity:
      print "auth'd osd %s is in state %s" % (entity, osd['state'])
      break
  else:
    print "auth'd osd %s doesn't exist" % entity
    if yesno == 'all':
      cmd = "echo ceph auth del %s" % entity
      print cmd
      print commands.getoutput(cmd)
    else:
      cmd = "echo ceph auth del %s" % entity
      yesno = raw_input("Should I run '%s' for you? [y,N,all]: " % cmd)
      if yesno.lower() in ('y','yes'):
        print cmd
        print commands.getoutput(cmd)
