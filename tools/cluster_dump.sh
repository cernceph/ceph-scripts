#!/usr/bin/env bash

CLUSTER="none"
SAVE_WHAT=""
PREFIX=""

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
        -c|--cluster)
            shift
            case "$1" in
                [a-zA-Z0-9_]*)
                    CLUSTER="$1"
                    ;;
                *)
                    echo "After -c, $1 doesn't look liek a cluster name"
                    exit 0
                    ;;
            esac
            ;;
        --pg|--osd|--crush)
            if grep -v "$1" <<< "$SAVE_WHAT" > /dev/null; then
                SAVE_WHAT="$SAVE_WHAT `sed 's/-//g' <<< "$1"`"
            fi
            ;;
        *)
            if test -f "$1"; then
                PREFIX="$1"
            else
                echo "Unknown argument: $1"
            fi
            ;;
    esac
    shift
done

if [[ $PREFIX == "" ]];
   echo "No target prefix found"
   exit 0
fi

if [[ $SAVE_WHAT == "" ]]; then
    SAVE_WHAT="pg osd crush"

get_target() {
    return  "$PREFIX_$1_`date +%s`"
}

for i in $SAVE_WHAT; do
    case $i in
        pg)
            ceph --cluster $CLUSTER pg dump > "$(get_target $i)"
            ;;
        osd)
            ceph --cluster $CLUSTER osd dump > "$(get_target $i)"
            ;;
        crush)
            ceph --cluster $CLUSTER osd getcrushmap | crushtool -d - > "$(get_target $i)"
            ;;
    esac
done

