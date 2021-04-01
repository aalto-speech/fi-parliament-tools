#!/usr/bin/env python3
# coding=utf-8
"""Command line client for preprocessing Finnish parliament transcripts."""
import json
from logging import Logger
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Set
from typing import TextIO
from typing import Union

from aalto_asr_preprocessor import preprocessor
from alive_progress import alive_bar

from fi_parliament_tools.transcriptParser.data_structures import EmbeddedStatement
from fi_parliament_tools.transcriptParser.data_structures import Statement
from fi_parliament_tools.transcriptParser.data_structures import Subsection
from fi_parliament_tools.transcriptParser.data_structures import Transcript


def apply_recipe(recipe: Any, transcripts: List[str], log: Logger, errors: List[str]) -> None:
    """Apply preprocessing recipe to each transcript and write result to a file.

    Also writes all unique Finnish words within the transcript to a file.

    Args:
        recipe (Any): a recipe file loaded as a module
        transcripts (list): paths to transcripts to preprocess
        log (Logger): for logging output
        errors (list): a list of error strings for reporting
    """
    with alive_bar(len(transcripts)) as bar:
        for transcript_path in transcripts:
            input_path = Path(transcript_path)
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
        log (Logger): for logging output
        errors (list): a list of error strings for reporting

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
                if not statement.language == "sv":
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


def decode_transcript(
    dct: Dict[Any, Any],
) -> Union[EmbeddedStatement, Statement, Subsection, Transcript, Dict[Any, Any]]:
    """Deserialize transcript json into a custom document object.

    Args:
        dct (dict): a (nested) dict in the JSON to deserialize

    Returns:
        documents.Object: the dictionary as a correct custom object
    """
    if "title" in dct.keys() and len(dct) == 4:
        return EmbeddedStatement(**dct)
    if "title" in dct.keys() and len(dct) > 4:
        return Statement(**dct)
    if "statements" in dct.keys():
        return Subsection(**dct)
    if "subsections" in dct.keys():
        return Transcript(**dct)
    return dct  # pragma: no cover
