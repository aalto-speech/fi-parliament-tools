#!/bin/bash

if [ $# -ne 2 ]; then
    echo "Usage: recipes/01_download_data.sh <start_session> <end_session>"
    echo "e.g.: $0 1/2020 10/2020"
    echo
    echo "Downloads sessions in the given range."
    echo
    exit
fi

if [ ! -d corpus ]; then
    echo "The directory 'corpus' (or a symbolic link to it) does not exist!"
    echo "Create directory/symbolic link before trying again."
    echo
    exit 1
fi

# An example of how to use the download client (use --help handle to find out more)
poetry run fi-parliament-tools download --start_session $START --end_session $END

echo "Next, compare the length of all audio files to their corresponding video file."
echo "Video download may have failed if the difference is over a minute."
for wav in $(find corpus/ -iname "*.wav"); do
    wav_length=$(soxi -D $wav)
    video_length=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of default=noprint_wrappers=1:nokey=1 ${wav/wav/mp4})
    # Compare only integers, decimals differ often and it is not relevant
    if (($(echo "${video_length%.*} - ${wav_length%.*} > 10" | bc -l))); then
        echo "The audio file $wav is over 10 seconds shorter than the mp4, ${wav_length%.*} vs. ${video_length%.*}"
    fi
done
