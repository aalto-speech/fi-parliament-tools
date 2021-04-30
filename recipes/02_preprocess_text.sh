#!/bin/bash

export LC_ALL=C

if [ $# -ne 3 ]; then
    echo "Usage: recipes/02_preprocess_text.sh <recipe> <corpus_dir> <transcript_list>"
    echo "e.g.: $0 /path/to/recipe_file /path/to/corpus_folder transcripts.list"
    echo
    echo "Preprocess parliament JSON transcripts in <transcript_list> into Kaldi text"
    echo "using <recipe>. Also produce a list of all the unique (Finnish) words that"
    echo "appear in the transcripts using .words files in <corpus_dir>."
    echo "To see examples of how to easily create the <transcript_list> file, see"
    echo "comments in this script."
    echo
    exit 1
fi

RECIPE=$1
CORPUS_DIR=$2
TRANSCRIPT_FILES=$3

# Examples of commands that can be used to generate the transcript file list automatically.
# Pick one.

# 1. Find all transcript JSONs.
# find $CORPUS_DIR -type f -name "*.json" | sort > transcripts.list

# 2. Find all JSON files changed/created within the last 5 days
# find $CORPUS_DIR -type f -name "*.json" -ctime -5 | sort > transcripts.list

# 3. Find all JSON files without corresponding preprocessed '.text' file.
# for f in $(find "${CORPUS_DIR}" -type f -name "*.json" | sort);
# do
#     [ ! -f "${f%.*}.text" ] && echo "$f" >> transcripts.list;
# done

# 4. Find recent video downloads and get the corresponding JSONs
# find $CORPUS_DIR -type f -name "*.wav" -ctime -3 | sed "s/wav/json/" > transcripts.list

# Call preprocessing script
poetry run fi-parliament-tools preprocess $TRANSCRIPT_FILES $RECIPE

# Sort all word files on their own first (Just printing all files to stdout with cat and sorting the
# stdout does not work. Some words vanish in the process for unknown reason unless files are
# presorted and merged. Maybe a memory issue?)
for f in $(find "${CORPUS_DIR}" -type f -name "*.words" | sort);
do
	sort -uo $f{,}
done
# Then merge all files and find unique words
UNFILTERED="unfiltered_words.txt"
sort -m -u $(find "${CORPUS_DIR}" -type f -name "*.words" | sort) > $UNFILTERED

# Filter the Swedish words that usually appear in transcript statements that are not explicitly
# labeled to be Swedish
comm -23 <(sort -u $UNFILTERED) <(sort -u recipes/swedish_words.txt) > new_vocab

# Cleanup
rm $TRANSCRIPT_FILES $UNFILTERED
find $CORPUS_DIR -type f -name "*.words" -delete
