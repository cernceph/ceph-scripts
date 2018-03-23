#!/usr/bin/env python
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
""" Print a list of nodes (of type osd/host/etc...) under a given CRUSH bucket/node.

Example:
    To see all osds in the "default" bucket:

        $ ceph_osds_in_bucket.py default

    To see all hosts in rack RJ31:

        $ ceph_osds_in_bucket.py --type host RJ31

"""

import commands
import simplejson as json
import argparse

def prepare(nodes):
    """ Iterate through all CRUSH nodes and prepare two hashes indexed by id and
        name.
    """
    by_id = {}
    by_name = {}
    for node in nodes:
        by_id[node['id']] = node
        by_name[node['name']] = node
    return by_id, by_name

def walk(node, bucket_type):
    """ Return a list of node names below this node, recursively if the node has
        children.
    """
    global nodes_by_id

    if node['type'] == bucket_type:
        return [node['name'],]
    if node['children']:
        children = []
        for child_id in node['children']:
            child = nodes_by_id[child_id]
            children = children + walk(child, bucket_type)
        return children
    else:  
      	return []

def list(bucket, type='osd'):
    global nodes_by_id

    tree = commands.getoutput('ceph osd tree -f json')
    all_nodes = json.loads(tree)['nodes']
    nodes_by_id, nodes_by_name = prepare(all_nodes)
    
    try:
        parent = nodes_by_name[bucket]
    except KeyError:
        raise Exception("Unknown CRUSH bucket '%s'" % bucket)
    
    return walk(parent, type)
    
if __name__ == "__main__":
    PARSER = argparse.ArgumentParser(
        description='Print a list of nodes in a given CRUSH bucket.')
    PARSER.add_argument('bucket', help='print all nodes below this CRUSH bucket')
    PARSER.add_argument('--type', default='osd',
                        help='search for nodes of this type')
    ARGS = PARSER.parse_args()

    FOUND = list(ARGS.bucket, ARGS.type)
    for f in FOUND:
        print f
