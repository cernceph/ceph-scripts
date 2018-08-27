#!/bin/bash
#
# Usage: ./extract_top_results.sh <path to files> <displaysize>
#



grep -E "\- writefull:" -R $1 -A 15 | grep -Eo "rbd_data.[a-z0-9]+" | sort | uniq -c | sort -h | tail -n "$2"
echo ""

grep -E "\- write:" -R $1 -A 15 | grep -Eo "rbd_data.[a-z0-9]+" | sort | uniq -c | sort -h | tail -n "$2"
echo ""

grep -E "\- read:" -R $1 -A 15 | grep -Eo "rbd_data.[a-z0-9]+" | sort | uniq -c | sort -h | tail -n "$2"
echo ""

