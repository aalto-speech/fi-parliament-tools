#!/bin/bash

if [ $# -ne 2 ]; then
	echo "This script synchronizes decoding and segmentation results required in the"
	echo "realignment process from a remote computing cluster. The script expects two"
	echo "arguments, path to the project folder locally and remotely:"
	echo "$0 /path/to/remote/project_folder /path/to/local/project_folder"
	exit 1
fi

SOURCE_DIR=$1
TARGET_DIR=$2

echo "Synchronize segmentation results from ${SOURCE_DIR}." 
rsync -Phauvz --exclude "**ivectors**" --exclude "*.gz" --exclude "*.mdl" --exclude "**.backup**" --exclude "**log**" --exclude "**split**" --exclude "**phones**" --exclude "**fsts**" --exclude "**temp**" -e "ssh" --chmod=g+s,g+rw --group=t405-puhe "${SOURCE_DIR}/generated/work" "${TARGET_DIR}/generated"
