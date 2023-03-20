#!/bin/bash

# This script will take in Finnish Parliament Corpus utterance ID
# and play the corresponding segment from the original session
# video file using VLC.

if [ $# -ne 1 ]; then
  echo "Usage: $0 <uttid>"
  echo "e.g.: $0 01302-005-2020-00127494-00128438"
  echo
  echo "Given a Finnish Parliament Corpus utterance ID, play corresponding"
  echo "segment of video using VLC."
  echo
  exit 1
fi

UTTID=$1

SESSION=${UTTID:6:8}
YEAR=${UTTID:10:4}
START=$(bc -l <<<"scale=2; ${UTTID:15:8} / 100")
END=$(bc -l <<<"scale=2; ${UTTID:24:8} / 100")
VIDEO="corpus/${YEAR}/session-${SESSION}.mp4"

vlc -q --play-and-exit --start-time=$START --stop-time=$END $VIDEO
