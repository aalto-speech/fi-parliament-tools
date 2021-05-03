"""Command line client for preprocessing Finnish parliament transcripts."""
import json
from logging import Logger
from pathlib import Path
from typing import Any
from typing import List
from typing import Set
from typing import TextIO

from aalto_asr_preprocessor import preprocessor
from alive_progress import alive_bar

from fi_parliament_tools.transcriptParser.data_structures import decode_transcript
from fi_parliament_tools.transcriptParser.data_structures import Transcript


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
