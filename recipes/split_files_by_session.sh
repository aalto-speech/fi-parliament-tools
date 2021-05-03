#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: recipes/split_files_by_session.sh <inputdir>"
    echo "e.g.: $0 generated/work/2021-01-01"
    echo
    echo "This script splits the ctm_edits.segmented, segments, and text files"
    echo "to session specific files, so we can do the realignment on a session-by-session"
    echo "basis."
    echo
    exit 1
fi

INPUT=$1

maindir=$(pwd)
outdir="generated/realign"
mkdir -p $outdir


echo "Move and write output to $outdir."
cd $outdir

# In the below awk commands, we find the 16 chars long session identifier on each line,
# and then print the line to a file that has the session ID in its name.
awk '{f=substr($0,match($0,/session-[0-9]{3}-[0-9]{4}/),16)".ctm_edits.segmented"; print > f}' $maindir/$INPUT/ctm_edits.segmented
awk '{f=substr($0,match($0,/session-[0-9]{3}-[0-9]{4}/),16)".segments"; print > f}' $maindir/$INPUT/segments
awk '{f=substr($0,match($0,/session-[0-9]{3}-[0-9]{4}/),16)".text"; print > f}' $maindir/$INPUT/text

echo "Splitting done, move back to $maindir."
cd $maindir

echo "Write input list for postprocessing to segments.list."
find $outdir -iname "*ctm_edits*" | sort > segments.list

echo "Done."
