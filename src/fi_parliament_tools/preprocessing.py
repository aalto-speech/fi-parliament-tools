"""Command line client for preprocessing Finnish parliament transcripts."""
import json
from dataclasses import asdict
from logging import Logger
from pathlib import Path
from typing import Any
from typing import List
from typing import Set
from typing import TextIO
from typing import Type
from typing import Union

import fasttext  # type: ignore
from aalto_asr_preprocessor import preprocessor
from alive_progress import alive_bar

from fi_parliament_tools.transcriptParser.data_structures import decode_transcript
from fi_parliament_tools.transcriptParser.data_structures import EmbeddedStatement
from fi_parliament_tools.transcriptParser.data_structures import Statement
from fi_parliament_tools.transcriptParser.data_structures import Transcript

FastTextModel = Type[fasttext.FastText._FastText]


def apply_fasttext_lid(
    lid_model: str, transcripts: List[str], log: Logger, errors: List[str]
) -> None:
    """Add missing language labels to statements using FastText LID model.

    Args:
        lid_model (str): path to the model binary
        transcripts (List[str]): transcripts to process
        log (Logger): logger object
        errors (List[str]): descriptions of all encountered errors
    """
    model = fasttext.load_model(lid_model)
    with alive_bar(len(transcripts)) as bar:
        for transcript_path in transcripts:
            input_path = Path(transcript_path).resolve()
            with input_path.open(mode="r", encoding="utf-8", newline="") as infile:
                transcript = json.load(infile, object_hook=decode_transcript)
            transcript = recognize_language(model, transcript)
            with input_path.open(mode="w", encoding="utf-8", newline="") as outfile:
                json.dump(asdict(transcript), outfile, ensure_ascii=False, indent=2)
            bar()


def recognize_language(model: FastTextModel, transcript: Transcript) -> Transcript:
    """Loop through transcript to recognize language for statements without language label.

    Args:
        model (FastTextModel): language identification model
        transcript (Transcript): transcript to process

    Returns:
        Transcript: updated transcript
    """
    for sub in transcript.subsections:
        for statement in sub.statements:
            if statement.text and not statement.language:
                statement.language = determine_language_label(model, statement)
            embedded = statement.embedded_statement
            if embedded.text and not embedded.language:
                embedded.language = determine_language_label(model, embedded)
    return transcript


def determine_language_label(
    model: FastTextModel, statement: Union[Statement, EmbeddedStatement]
) -> str:
    """Predict and select language label for the statement.

    Assume statement is Finnish if predicted labels do not contain either Finnish or Swedish.
    Some statements have both Finnish and Swedish speech in them which is why top two labels
    are predicted. The '.p' notation is used to differentiate predicted labels from true labels.

    Args:
        model (FastTextModel): language identification model
        statement (Union[Statement, EmbeddedStatement]): statement to label

    Returns:
        str: selected language label
    """
    labels, _ = model.predict(statement.text, k=2)
    labels = [label.replace("__label__", "") for label in labels]
    label = "fi.p"
    if "fi" in labels and "sv" in labels:
        label = "fi+sv.p"
    elif "sv" in labels:
        label = "sv.p"
    return label


def apply_recipe(recipe: Any, transcripts: List[str], log: Logger, errors: List[str]) -> None:
    """Apply preprocessing recipe to each transcript and write result to a file.

    Also writes all unique Finnish words within the transcript to a file.

    Args:
        recipe (Any): a recipe file loaded as a module
        transcripts (list): paths to transcripts to preprocess
        log (Logger): logger object
        errors (list): descriptions of all encountered errors
    """
    with alive_bar(len(transcripts)) as bar:
        for transcript_path in transcripts:
            input_path = Path(transcript_path).resolve()
            with input_path.open(mode="r", encoding="utf-8", newline="") as infile:
                transcript = json.load(infile, object_hook=decode_transcript)
            t = input_path.with_suffix(".text")
            w = input_path.with_suffix(".words")
            with t.open("w", encoding="utf-8", newline="") as textfile, w.open(
                "w", encoding="utf-8", newline=""
            ) as wordfile:
                bytecount = textfile.write(input_path.stem)
                unique_words = preprocess_transcript(recipe, transcript, textfile, log, errors)
                if textfile.tell() == bytecount:
                    errors.append(f"Preprocessing output was empty for {input_path.stem}.")
                wordfile.writelines("\n".join(unique_words))
            bar()


def preprocess_transcript(
    recipe: Any, transcript: Transcript, outfile: TextIO, log: Logger, errors: List[str]
) -> Set[str]:
    """Preprocess and write a transcript to a file given a recipe and return unique Finnish words.

    Note that some words in Swedish and other languages will get included in the word lists because
    MPs occasionally borrow sayings from other languages. Additionally, the language parameter is
    not defined for chairman statements which is why the Swedish words in those statements get
    included too.

    Args:
        recipe (Any): a recipe file loaded as a module
        transcript (Transcript): a transcript to preprocess
        outfile (TextIO): a file handle for writing output
        log (Logger): logger object
        errors (list): descriptions of all encountered errors

    Returns:
        set: a set of unique Finnish words within the transcript
    """
    unique_words: Set[str] = set()
    for sub in transcript.subsections:
        for statement in sub.statements:
            txt = statement.text
            if statement.embedded_statement.text:
                txt = txt.replace("#ch_statement", statement.embedded_statement.text)
            try:
                txt = preprocessor.apply(
                    txt, recipe.REGEXPS, recipe.UNACCEPTED_CHARS, recipe.TRANSLATIONS
                )
                if "fi" in statement.language:
                    unique_words = unique_words.union(set(txt.split()))
                outfile.write(" " + txt.lower())
            except preprocessor.UnacceptedCharsError as e:
                log.debug(f"Error message for {outfile.name}:\n {e}")
                errors.append(f"UnacceptedCharsError in {outfile.name}. See log for debug info.")
            except Exception:
                log.exception(
                    f"Preprocessing failed in {outfile.name} in statement beginning at "
                    f"'{statement.start_time}'."
                )
                errors.append(f"Caught an exception in {outfile.name}.")
    return unique_words
