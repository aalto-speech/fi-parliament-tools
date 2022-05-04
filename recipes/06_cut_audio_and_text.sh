#!/bin/bash

if [ $# -ne 3 ]; then
    echo "Usage: recipes/06_cut_audio_and_text.sh <kaldi_dir> <output_dir> <num_lines>"
    echo "e.g.: $0 final_outputs/fi-parl-autumn2020 final_outputs/fi-parl-autumn2020/wavs_and_trns 200000"
    echo
    echo "This script cuts the segments in <kaldi_dir> to individual wav-files, gets the"
    echo "text, and writes the sample pairs into <output_dir>. The script will split the"
    echo "segments file in <kaldi_dir> to smaller files with max <num_lines>. The resulting"
    echo "smaller files will be processed in parallel."
    echo
    echo "NOTE: Ensure you have diskspace for the sample pairs before running this."
    echo
    exit 1
fi

INPUT=$1
OUTPUT=$2
NUM=$3

cut_wavs() {
    while read p; do
        name=$(echo $p | cut -f1 -d" ")
        sess=$(echo $p | cut -f2 -d" ")
        start=$(echo $p | cut -f3 -d" ")
        end=$(echo $p | cut -f4 -d" ")
        wav=$(grep $sess $2)
        folder="$4/$sess"
        mkdir -p $folder
        segment_wav="${name}.wav"
        sox $wav $folder/$segment_wav trim $start =$end
        segment_trn="${name}.trn"
        grep $name $3/text | cut -f2- -d" " >$folder/$segment_trn
    done <$1
    echo "Finished with $1"
}

segments_file=$INPUT/segments
wavs="wav_paths"

awk '{print $2}' $INPUT/wav.scp >$wavs

split -l $NUM -d $segments_file $INPUT/segments_part_

echo "Splitted segments to smaller subset files: " $INPUT/segments_part_*
for part_file in $INPUT/segments_part_*; do
    cut_wavs $part_file $wavs $INPUT $OUTPUT &
done

echo "Started cutting jobs for all subsets on the background."
