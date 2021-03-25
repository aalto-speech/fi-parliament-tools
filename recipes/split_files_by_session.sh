#!/bin/bash

# This script splits the ctm_edits.segmented, segments, and text files to session specific
# files, so we can do the realignment on a session-by-session basis.

maindir=$(pwd)

for workdir in generated/work/*h
do
    length="${workdir##*/}"
    tmpdir="generated/realign_tmp/$length"
    mkdir -p $tmpdir
    cd $tmpdir

    # In the below awk commands, we find the 16 chars long session identifier on each line,
    # and then print the line to a file that has the session ID in its name.
    awk '{f=substr($0,match($0,/session-[0-9]{3}-[0-9]{4}/),16)"_ctm_edits.segmented"; print > f}' $maindir/$workdir/ctm_edits.segmented
    awk '{f=substr($0,match($0,/session-[0-9]{3}-[0-9]{4}/),16)"_segments"; print > f}' $maindir/$workdir/segments
    awk '{f=substr($0,match($0,/session-[0-9]{3}-[0-9]{4}/),16)"_text"; print > f}' $maindir/$workdir/text

    cd $maindir
done
