#!/usr/bin/env bash

UP_PATH=/tmp/last_upmaps
UP_CMD="ceph osd dump | grep upmap_items | sort"

while test $# -gt 0; do
    case "$1" in
        -h|--help)
            echo "This script saves the upmaps of the cluster."
            echo "When a change is done, run this script again"
            echo "to load the lost upmaps."
            echo
            echo "  -h/--help        Show this message"
            echo "  -s/--save        Save the upmaps"
            echo "  -l/--load        Load lost upmaps"
            echo
            exit 0
            ;;
        -s|--save)
            if eval $UP_CMD > $UP_PATH; then
                echo "Saved upmaps sucessfully at $UP_PATH"
            else
                echo "Error occured while trying to save upmaps at $UP_PATH"
                exit 0
            fi
            ;;
        -l|--load)
            TMPFILE=mktemp
            if eval $UP_CMD > $TMPFILE; then
                diff $UP_PATH $TMPFILE | grep -Po '(?<=< )pg.*' | sed -e 's/_/-/g' -e 's/\[\|\]//g' -e 's/,/ /g' | xargs -L1 ceph osd
            else
                echo "Error occured while trying to get current upmaps"
            fi
            rm -f $TMPFILE
            ;;
        *)
            echo "Unknown argument: $1"
    esac
    shift
done
