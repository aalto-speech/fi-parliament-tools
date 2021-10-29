#!/bin/bash

if [ $# -ne 2 ]; then
	echo "Usage: recipes/sync_from_remote.sh <from_dir> <to_dir>"
	echo "e.g.: $0 /path/to/remote/project_folder/generated/work ./generated"
	echo
	echo "This script synchronizes decoding and segmentation results required in the"
	echo "realignment process from a remote computing cluster."
	echo "Note that script expects these results to be under the directory generated/work"
	echo "at the remote location."
	echo
	exit 1
fi

SOURCE_DIR=$1
TARGET_DIR=$2

echo "Synchronize segmentation results from ${SOURCE_DIR}."
rsync -Pharumvz --include "*/" --include "/*/*/segments" --include "text" --include "ctm_edits.segmented" --exclude "*" -e "ssh" --chmod=g+s,g+rw --group=t405-puhe ${SOURCE_DIR} ${TARGET_DIR}

# Ensure read and write permissions for file owner and team members
find $TARGET_DIR -user $(echo $USER) -exec chmod ug+rw {} \;

