#!/usr/bin/env bash

MAX_CAPS=$(ceph daemon mds.`hostname -s` config show | jq -r .mds_max_caps_per_client)
ceph daemon mds.`hostname -s` session ls | jq ".[]|select(.num_caps>$((5*MAX_CAPS)))"
