#!/bin/bash

if [ $# -ne 2 ]; then
	echo "Usage: recipes/sync_to_remote.sh <from_dir> <to_dir>"
	echo "e.g.: $0 /path/to/local/corpus_folder /path/to/remote/corpus_folder"
	echo
	echo "This script synchronizes the contents of the corpus folder (.wav, .text, & .mp4)" 
	echo "to a remote server using rsync. Needed only if you use a computing cluster for"
	echo "the decoding and segmentation part."
	echo
	exit 1
fi

SOURCE_DIR=$1
REMOTE_DIR=$2

echo "Start by synchronizing wav and (preprocessed) text files first because it is much faster." 
rsync -Phauvz --include '*/' --include '*.wav' --include '*.text' --exclude '*' -e "ssh" --chmod=g+s,g+rw --group=t405-puhe $SOURCE_DIR $REMOTE_DIR

echo "Moving on to synchronizing mp4 files. This will take time." 
rsync -Phauv --include '*/' --include '*.mp4' --exclude '*' -e "ssh" --chmod=g+s,g+rw --group=t405-puhe $SOURCE_DIR $REMOTE_DIR

# Handle notes:
# -P outputs progress and makes it possible to continue an interrupted rsync which is helpful with big transfers
# -h human-readable file sizes and transfer speeds
# -a keep permissions and timestamps
# -u prevents overwrite of files that have been changed at Triton
# -v verbose output
# -z compress files before transfer to save bandwith

# Other potentially useful handles
# -n dry-run, see what will be done but do not execute
# -vv/-vvv increased verbosity, helpful if it seems that rsync hangs at some point
# -c compute checksums if you suspect files have been corrupted. Computing md5sums for the big video files in this folder takes ages, so apply only to small number of files. 

