#!/usr/bin/env python

import rados, sys

cluster = rados.Rados(conffile='/etc/ceph/ceph.conf')
cluster.connect()
print "\nCluster ID: " + cluster.get_fsid()
ioctx = cluster.open_ioctx('test')

object_iterator = ioctx.list_objects()

while True :
  try :
    object = object_iterator.next()
    if 'benchmark_data_' in object.key:
      print "Removing object", object.key
      #object.remove()
      ioctx.aio_remove(object.key)
  except rados.ObjectNotFound:
    print object.key, 'not found'
    pass
  except StopIteration :
    break

print "\nFlushing the context."
ioctx.aio_flush()
print "\nClosing the connection."
ioctx.close()
