#!/bin/bash

if [ $# -ne 2 ]; then
    echo "Usage: recipes/01_download_data.sh <start_session> <end_session>"
    echo "e.g.: $0 1/2020 10/2020"
    echo
    echo "Downloads sessions in the given range."
    echo
    exit
fi

START=$1
END=$2

if [ ! -d corpus ]; then
    echo "The directory 'corpus' (or a symbolic link to it) does not exist!"
    echo "Create directory/symbolic link before trying again."
    echo
    exit 1
fi

# An example of how to use the download client (use --help handle to find out more)
fi-parliament-tools download --start_session $START --end_session $END

# Ensure read and write permissions for file owner and team members
find corpus/ -user $(echo $USER) -exec chmod ug+rw {} \;
