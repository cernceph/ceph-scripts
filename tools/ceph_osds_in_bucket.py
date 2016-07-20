#!/usr/bin/env python
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
""" Print a list of OSDs under a given CRUSH bucket/node.

Example:
    To see all nodes in the "default" bucket:

        $ ceph_osds_in_bucket.py default
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

def walk(node):
    """ Print the OSD names below this node, recursively if the node has
        children.
    """
    if node['type'] == 'osd':
        print node['name']
        return
    if node['children']:
        for child_id in node['children']:
            child = NODES_BY_ID[child_id]
            walk(child)

if __name__ == "__main__":
    PARSER = argparse.ArgumentParser(
        description='Print a list of OSDs in a given CRUSH bucket/node.')
    PARSER.add_argument('bucket', help='print all OSDs below this CRUSH bucket')
    ARGS = PARSER.parse_args()
    PARENT_NAME = ARGS.bucket

    TREE = commands.getoutput('ceph osd tree -f json')
    NODES = json.loads(TREE)['nodes']
    NODES_BY_ID, NODES_BY_NAME = prepare(NODES)

    try:
        PARENT = NODES_BY_NAME[PARENT_NAME]
    except KeyError:
        raise Exception("Unknown CRUSH bucket '%s'" % PARENT_NAME)

    walk(PARENT)

