#!/bin/bash

if [ $# -ne 3 ]; then
    echo "Usage: recipes/sample_segments.sh <num> <kaldi_dir> <output_tar>"
    echo "e.g.: $0 20 generated/new_data sample_filename"
    echo
    echo "This script picks <num> samples from the segments in <kaldi_dir>, gets the"
    echo "corresponding audio and text, and packs the samples into a tar archive <output_tar>."
    echo
    exit 1
fi

NUM=$1
INPUT=$2
OUTPUT=$3

samples="samples.list"
utts="sampled_utts"
records="sampled_records"
wavs="sampled_wavs"
texts="sampled_texts"

shuf -n $NUM $INPUT/segments | sort > $samples

awk '{print $1}' $samples > $utts
awk '{print $2}' $samples > $records

grep -f $utts $INPUT/text | sort > $texts
grep -f $records $INPUT/wav.scp | sort | awk '{print $2}' > $wavs

tar -cf $OUTPUT $texts

while read p;
do
    name=$(echo $p | cut -f1 -d" ")
    sess=$(echo $p | cut -f2 -d" ")
    start=$(echo $p | cut -f3 -d" ")
    end=$(echo $p | cut -f4 -d" ")
    wav=$(grep $sess $wavs)
    sample_wav="${name}.wav"
    sox $wav $sample_wav trim $start =$end
    tar -rf $OUTPUT $sample_wav
    rm $sample_wav
done < $samples

rm $samples $utts $records $wavs $texts
