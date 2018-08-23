#!/bin/bash
#
# Usage: ./extract_top_results.sh <path to files> <displaysize>
#



grep -E "\- writefull:" $1 -A 15 | grep -Eo "rbd_data.[a-z0-9]+" | sort | uniq -c | sort -h | tail -n $2
grep -E "\- write:" $1 -A 15 | grep -Eo "rbd_data.[a-z0-9]+" | sort | uniq -c | sort -h | tail -n $2
grep -E "\- read:" $1 -A 15 | grep -Eo "rbd_data.[a-z0-9]+" | sort | uniq -c | sort -h | tail -n $2
