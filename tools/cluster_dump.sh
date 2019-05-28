#!/usr/bin/env bash

# Licence: MIT
# Created by: Theofilos Mouratidis <t.mour@cern.ch>
# Date: 2019/05/24

CLUSTER="ceph"
SAVE_WHAT=""
PREFIX=""

#
# creates an entry that executes a ceph command
# eg the first one:
#   * Creates the --pg argument
#   * The first part is what will be executed after "ceph"
#     - In this example it will execute "ceph pg dump"
#   * The second part is the argument description
#   * Use ",," as a separator betwwen command and description
# each k/v pair will create both the argument functionality
# and the entry in the --help page
#
declare -A CMD=(
    ["pg"]="pg dump ,, Saves the pg state"
    ["pg-json"]="pg dump -f json-pretty ,, Saves the pg state"
    ["osd"]="osd dump ,, Saves the osd state"
    ["osd-json"]="osd dump -f json-pretty ,, Saves the osd state"
    ["crush"]="osd getcrushmap 2> /dev/null | crushtool -d - ,, Saves the crushmap"
    ["tree"]="osd tree ,, Saves the osd tree"
    ["tree-json"]="osd tree -f json-pretty ,, Saves the osd tree"
    ["df"]="osd df ,, Saves the osd df"
    ["df-json"]="osd df -f json-pretty ,, Saves the osd df"
)

while test $# -gt 0; do
    case "$1" in
        -h|--help)
            echo "This script saves various data from ceph commands"
            echo "mainly used to log critical data for recovery reasons"
            echo
            echo "Example command: cluster_dump -a -c erin /tmp/out"
            echo "It will dump all the below commands to the /tmp/out_* prefix"
            echo
            # Use \t to align your fields in the table
            OUT=""
            OUT="$OUT\n  -h/--help\t\tShow this message"
            OUT="$OUT\n  -c/--cluster\t<name>\tSelect cluster"
            OUT="$OUT\n  -a/--all\t\tDump all below commands"
            echo -e "$OUT" | column -ts $'\t'
            echo
            # Auto gen, don't edit
            echo " COMMANDS:"
            OUT=""
            for key in ${!CMD[@]}; do
                OUT="$OUT\n  --$key\t${CMD[$key]##*",,"}"
            done
            echo -e "$OUT" | column -ts $'\t' -o $'\t\t'
            echo
            exit 0
            ;;
        # Can define additional arguments with custom functionality as:
        # -m|--mycommand)
        #   do_stuff
        # ;;
        # for main functionality just use the $CMD dictionary above
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
        -a|--all)
            if [[ $SAVE_WHAT == "" ]]; then
                SAVE_WHAT="all"
            else
                echo "All flag is incompatible with these others: $SAVE_WHAT"
                exit 0
            fi
            ;;
        *)
            found=false
            if [[ "$1" =~ ^- ]]; then
                if [[ "$1" =~ ^-- ]]; then
                    ARG="${1//-}"
                    if [[ "${!CMD[@]}" =~ "$ARG" ]]; then
                        if [[ "$SAVE_WHAT" =~ "all" ]]; then
                            echo "All flag is incompatible with these others: $ARG"
                            exit 0
                        fi
                        if grep -v "$ARG" <<< "$SAVE_WHAT" > /dev/null; then
                            SAVE_WHAT="$SAVE_WHAT $ARG"
                            found=true
                        fi
                    fi
                fi
                if [[ $found == false ]]; then
                    echo "Unknown argument $ARG"
                    exit 0
                fi
            elif touch "$1" > /dev/null 2>&1; then
                if test -d "$1"; then
                    if [[ "${1: -1}" != "/" ]]; then
                        PREFIX="$1/"
                    else
                        PREFIX="$1"
                    fi
                elif test -f "$1"; then
                    PREFIX="$1_"
                fi
            else
                echo "Parent path does not exist: $1"
                exit 0
            fi
            ;;
    esac
    shift
done

if [[ $PREFIX == "" ]]; then
   echo "Error with output file prefix"
   exit 0
fi

if [[ $SAVE_WHAT == "all" ]]; then
    SAVE_WHAT="${!CMD[@]}"
elif [[ $SAVE_WHAT == "" ]]; then
    echo "No action is defined. Check what to do with -h/--help"
    exit 0
fi

exec_cmd() {
    eval "ceph --cluster $CLUSTER $1 > ${PREFIX}${CLUSTER}_$2_$(date +%Y%m%d_%H%M) 2>> /var/log/ceph/cluster_dump.log"
}

for key in $SAVE_WHAT; do
    exec_cmd "${CMD[$key]%%",,"*}" $key
done
