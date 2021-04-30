#!/bin/bash

if [ $# -ne 3 ]; then
    echo "Usage: recipes/create_final_kaldi_files.sh <input_dir> <output_dir> <corpus_dir>"
    echo "e.g.:  $0 generated/segmented_sessions generated/new_data path/to/corpus"
    echo
    echo "This script creates combined Kaldi files for all session Kaldi files in <input_dir>."
    echo "Output is saved in <output_dir>. <corpus_dir> is a path to the folder which contains"
    echo "all the wav files arranged into folders by year."
    echo
    exit 1
fi

INPUT=$1
OUTPUT=$2
CORPUS=$3

mkdir -p $OUTPUT

# Sort and merge new segments
# (This approach is copied from 02_preprocess_text, see there for reasoning.)
for f in $(find "${INPUT}" -type f -name "*segments_new" | sort);
do
	sort -uo $f{,}
done
sort -m -u $(find "${INPUT}" -type f -name "*segments_new" | sort) > $OUTPUT/segments

# text
for f in $(find "${INPUT}" -type f -name "*text_new" | sort);
do
	sort -uo $f{,}
done
sort -m -u $(find "${INPUT}" -type f -name "*text_new" | sort) > $OUTPUT/text

# wav.scp
awk 'BEGIN { FS=" " } { print $2 }' $OUTPUT/segments | sort -u > $OUTPUT/wav
awk -v corp=$CORPUS 'BEGIN { FS="-" } { print $1"-"$2" "corp"/"$2"/session-"$1"-"$2".wav" }' $OUTPUT/wav > $OUTPUT/wav.scp

# utt2spk
awk '{ print $1 }' $OUTPUT/segments > $OUTPUT/utt
awk 'BEGIN { FS="-" } { print $0" "$1 }' $OUTPUT/utt > $OUTPUT/utt2spk

rm $OUTPUT/utt $OUTPUT/wav
