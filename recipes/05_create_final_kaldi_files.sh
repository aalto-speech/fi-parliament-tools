#!/bin/bash

export LC_ALL=C

if [ $# -ne 3 ]; then
    echo "Usage: recipes/04_create_final_kaldi_files.sh <input_dir> <output_dir> <corpus_dir>"
    echo "e.g.:  $0 generated/realign generated/new_data path/to/corpus"
    echo
    echo "This script creates combined Kaldi files for all session Kaldi files in <input_dir>."
    echo "Output is saved in <output_dir>. <corpus_dir> is a path to the folder which contains"
    echo "all the wav files arranged into folders by year. The corpus path is used to write"
    echo "wav.scp file so absolute path is preferable."
    echo
    exit 1
fi

INPUT=$1
OUTPUT=$2
CORPUS=$3

mkdir -p $OUTPUT

# Sort and merge new segments
# (This approach is copied from 02_preprocess_text, see there for reasoning.)
echo "Compile $OUTPUT/segments file."
for f in $(find "${INPUT}" -type f -name "*segments.new" | sort);
do
	sort -uo $f{,}
done
sort -m -u $(find "${INPUT}" -type f -name "*segments.new" | sort) > $OUTPUT/segments

# text
echo "Compile $OUTPUT/text file."
for f in $(find "${INPUT}" -type f -name "*text.new" | sort);
do
	sort -uo $f{,}
done
# sed is needed for the double spaces outputted by the CSV writer of Python
# when it is made to output a file like Kaldi text (that is not a csv file)
sort -m -u $(find "${INPUT}" -type f -name "*text.new" | sort) | sed 's/  / /g' > $OUTPUT/text

# Crudely filter remaining Swedish segments using high frequency Swedish words.
# Some statements marked as Finnish have Swedish in them too which is not caught
# by the postprocessing pipeline.
echo "Try to filter most of remaining segments with Swedish from segments and text."
echo "Filtered Swedish will be outputted to $OUTPUT/filtered_swedish"
grep -P " (jag|vi|er|man|de[nt]|är|har|var|hade|inte|på|så|som|men|att|vid|och|ledamot) " $OUTPUT/text > $OUTPUT/filtered_swedish.text
awk '{print $1}' $OUTPUT/filtered_swedish.text > $OUTPUT/swedish_uttids
grep -f $OUTPUT/swedish_uttids $OUTPUT/segments > $OUTPUT/filtered_swedish.segments
while read p
do
    sed -i "/$p/d" $OUTPUT/text
    sed -i "/$p/d" $OUTPUT/segments
done < $OUTPUT/swedish_uttids

# wav.scp
echo "Compile $OUTPUT/wav.scp file."
awk 'BEGIN { FS=" " } { print $2 }' $OUTPUT/segments | sort -u > $OUTPUT/wav
awk -v corp=$CORPUS 'BEGIN { FS="-" } { print $1"-"$2" "corp"/"$2"/session-"$1"-"$2".wav" }' $OUTPUT/wav > $OUTPUT/wav.scp

# utt2spk
echo "Compile $OUTPUT/utt2spk file."
awk '{ print $1 }' $OUTPUT/segments > $OUTPUT/utt
awk 'BEGIN { FS="-" } { print $0" "$1 }' $OUTPUT/utt > $OUTPUT/utt2spk

# spk2utt
echo "Compile $OUTPUT/spk2utt file."
awk '{ utts[$2] = utts[$2]" "$1 } END { for (speaker in utts) print speaker utts[speaker] }' utt2spk

echo "Clean intermediary files."
rm $OUTPUT/utt $OUTPUT/wav $OUTPUT/swedish_uttids

echo "Finished with $(wc -l $OUTPUT/segments | cut -f1 -d' ') segments in $OUTPUT/segments."
