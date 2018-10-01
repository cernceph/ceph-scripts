#!/bin/bash
# fix images affected by http://tracker.ceph.com/issues/16211
# Credit to Wido
set -e

POOL=$1
IMAGE=$2

ID=$(rados -p $POOL get rbd_id.$IMAGE -|strings)

rados -p $POOL setomapval rbd_header.${ID} dummy_key dummy_val

rbd -p $POOL info $IMAGE
