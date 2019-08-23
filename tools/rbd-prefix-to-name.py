#!/usr/bin/python

from optparse import OptionParser
import rados
import sys

def rbd_prefix_to_name(options):
  assert(options.prefix.startswith('rbd_data.'))
  key = options.prefix.replace('rbd_data.','id_')
  pool = options.pool
  cluster = rados.Rados(conffile='/etc/ceph/ceph.conf')
  cluster.connect()
  ioctx = cluster.open_ioctx(pool)
  with rados.ReadOpCtx(ioctx) as read_op:
    iter, ret = ioctx.get_omap_vals_by_keys(read_op,(key,))
    assert(ret == 0)
    ioctx.operate_read_op(read_op, "rbd_directory")
    try:
      print list(iter)[0][1][4:]
    except IndexError:
      print 'Error: %s not found in pool %s' % (key, pool)
      sys.exit(-1)


if __name__ == "__main__":
  parser = OptionParser()
  parser.add_option("-P", "--prefix", dest="prefix", type="string",
                  help="RBD object prefix to lookup")
  parser.add_option("-p", "--pool", dest="pool", type="string", default="volumes",
                  help="Ceph pool (default: volumes)")
  (options, args) = parser.parse_args()
  if not options.prefix:
    parser.error('PREFIX not given')

  rbd_prefix_to_name(options)
