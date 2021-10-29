#!/bin/bash

# This a convenience script for checking that video and audio lengths
# roughly match if there is suspicion of broken audio files or similar.

if [ ! -d corpus ]; then
    echo "The directory 'corpus' (or a symbolic link to it) does not exist!"
    echo "Assuming therefore that there is nothing to check."
    echo
    exit 1
fi

echo "Comparing the length of all audio files to their corresponding video file."
echo "Will report only if over 10 second differences are found."

for wav in $(find corpus/ -iname "*.wav"); do
    wav_length=$(soxi -D $wav)
    video_length=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 ${wav/wav/mp4})
    # Compare only integers, decimals differ often and it is not relevant
    if (($(echo "${video_length%.*} - ${wav_length%.*} > 10" | bc -l))); then
        echo "The audio file $wav is over 10 seconds shorter than the mp4, ${wav_length%.*} vs. ${video_length%.*}"
    fi
done

echo "Finished comparisons."
