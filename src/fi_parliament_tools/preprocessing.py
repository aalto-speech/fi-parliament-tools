"""Command line client for preprocessing Finnish parliament transcripts."""
import json
from dataclasses import asdict
from logging import Logger
from pathlib import Path
from typing import IO
from typing import Any
from typing import List
from typing import Set
from typing import Tuple
from typing import Type
from typing import Union

import fasttext  # type: ignore
import pandas as pd
from aalto_asr_preprocessor import preprocessor
from alive_progress import alive_bar
from atomicwrites import atomic_write

from fi_parliament_tools.parsing.data_structures import EmbeddedStatement
from fi_parliament_tools.parsing.data_structures import Statement
from fi_parliament_tools.parsing.data_structures import Transcript
from fi_parliament_tools.parsing.data_structures import decode_transcript
from fi_parliament_tools.pipeline import Pipeline


FastTextModel = Type[fasttext.FastText._FastText]


class PreprocessingPipeline(Pipeline):
    """Preprocess given parliament transcripts.

    Preprocessing of parliament transcripts consists of three parts:
        1. Predict language labels for statements without them.
        2. Add MP ids to chairman statements using MP table.
        3. Preprocess and clean statement texts for automatic speech recognition.

    Preprocessed statement texts will be saved in Kaldi text format.
    """

    def __init__(
        self, log: Logger, transcript_paths: List[str], lid_model: str, mptable: str, recipe: Any
    ) -> None:
        """Initialize common parameters and preprocessing specific parameters.

        Args:
            log (Logger): logger object
            transcript_paths (List[str]): parliament transcripts (.json) to process
            lid_model (str): path to LID model for predicting text language
            mptable (str): path to CSV table of MP information
            recipe (Any): a preprocessing recipe file loaded as a module
        """
        super().__init__(log)
        self.transcript_paths = [Path(path).resolve() for path in transcript_paths]
        self.lid = fasttext.load_model(lid_model)
        self.recipe = recipe
        self.mptable = pd.read_csv(mptable, sep="|", index_col="mp_id")

    def load_transcript(self, path: Path) -> Transcript:
        """Load Transcript object from a JSON file at input path.

        Args:
            path (Path): path to a JSON transcript file

        Returns:
            Transcript: loaded transcript object
        """
        with path.open(mode="r", encoding="utf-8", newline="") as infile:
            transcript: Transcript = json.load(infile, object_hook=decode_transcript)
        return transcript

    def write_transcript_and_words(
        self, path: Path, transcript: Transcript, unique_words: Set[str]
    ) -> None:
        """Write updated transcript to the JSON file and list of unique words to a .words file.

        Args:
            path (Path): path to the original JSON file
            transcript (Transcript): updated transcript
            unique_words (Set[str]): list of unique words in the transcript
        """
        with atomic_write(path, mode="w", overwrite=True, encoding="utf-8", newline="") as jsonf:
            json.dump(asdict(transcript), jsonf, ensure_ascii=False, indent=2)
        with atomic_write(path.with_suffix(".words"), mode="w", encoding="utf-8") as wordf:
            wordf.write("\n".join(unique_words))

    def run(self) -> None:
        """Run preprocessing pipeline over the input file list."""
        with alive_bar(len(self.transcript_paths)) as bar:
            for path in self.transcript_paths:
                transcript = self.load_transcript(path)
                with atomic_write(path.with_suffix(".text"), mode="w", encoding="utf-8") as textf:
                    bytecount = textf.write(path.stem)
                    transcript, unique_words = self.preprocess_transcript(transcript, textf, path)
                    if textf.tell() == bytecount:
                        self.log.warning(f"Preprocessing output was empty for {path.stem}.")
                self.write_transcript_and_words(path, transcript, unique_words)
                bar()

    def preprocess_transcript(
        self, transcript: Transcript, textfile: IO[Any], path: Path
    ) -> Tuple[Transcript, Set[str]]:
        """Preprocess transcript for segmentation.

        Preprocessing has three steps:
        1. Recognize language for statements without language label.
        2. Add MP ids to statement without MP ids (chairman statements).
        3. Preprocess statement texts to Kaldi-style text files.

        Args:
            transcript (Transcript): transcript to update
            textfile (IO[Any]): a file handle for writing output
            path: (Path): path to the input JSON

        Returns:
            Tuple[Transcript, Set[str]]: preprocessed transcript and a set of unique words in it
        """
        unique_words: Set[str] = set()
        for sub in transcript.subsections:
            for statement in sub.statements:
                self.recognize_language(statement)
                self.update_missing_mpids(statement, path)
                new_words = self.preprocess_statement(statement, textfile, path)
                unique_words = unique_words.union(new_words)
        return transcript, unique_words

    def recognize_language(self, statement: Statement) -> None:
        """Recognize language for a statement (and its embedded statement).

        Args:
            statement (Statement): statement to recognize
        """
        if statement.text and not statement.language:
            statement.language = self.determine_language_label(statement)
        embedded = statement.embedded_statement
        if embedded.text and not embedded.language:
            embedded.language = self.determine_language_label(embedded)

    def determine_language_label(self, statement: Union[Statement, EmbeddedStatement]) -> str:
        """Predict and select language label for the statement.

        Assume statement is Finnish if predicted labels do not contain either Finnish or Swedish.
        Some statements have both Finnish and Swedish speech in them which is why top two labels
        are predicted. The '.p' notation is used to differentiate predicted labels from true labels.

        Args:
            statement (Union[Statement, EmbeddedStatement]): statement to label

        Returns:
            str: selected language label
        """
        labels, _ = self.lid.predict(statement.text, k=2)
        labels = [label.replace("__label__", "") for label in labels]
        label = "fi.p"
        if "fi" in labels and "sv" in labels:
            label = "fi+sv.p"
        elif "sv" in labels:
            label = "sv.p"
        return label

    def update_missing_mpids(self, statement: Statement, path: Path) -> None:
        """Update missing MP id value in statement and its embedded statement.

        Args:
            statement (Statement): statement to update
            path (Path): transcript JSON path for logging needs
        """
        try:
            if statement.mp_id == 0 and statement.firstname:
                statement.mp_id = self.lookup_mpid(statement)
            embedded = statement.embedded_statement
            if embedded.mp_id == 0 and embedded.firstname:
                embedded.mp_id = self.lookup_mpid(embedded)
        except KeyError as e:
            self.log.debug(f"Unknown MP in {path} in statement at '{statement.start_time}':\n {e}")
            self.errors.append(f"Encountered unknown MP in {path}. See log for more info.")

    def lookup_mpid(self, statement: Union[Statement, EmbeddedStatement]) -> int:
        """Look up MP id in the MP table using MP name.

        Args:
            statement (Union[Statement, EmbeddedStatement]): statement without MP id

        Raises:
            KeyError: MP not found in MP table

        Returns:
            int: found MP id
        """
        lookup = self.mptable.index[
            (self.mptable.firstname == statement.firstname)
            & (self.mptable.lastname == statement.lastname)
        ]
        if lookup.empty:
            raise KeyError(
                f"Cannot find MP named {statement.firstname} {statement.lastname} in the MP table. "
                "Potential causes: typo in the name, the statement speaker is not an MP or your MP "
                "table is outdated."
            )
        return int(lookup[0])

    def preprocess_statement(self, statement: Statement, textfile: IO[Any], path: Path) -> Set[str]:
        """Preprocess and write statement to a file given a recipe and return unique Finnish words.

        Note that some words in Swedish and other languages will get included in the word lists
        because MPs occasionally borrow sayings from other languages. Additionally, the language
        parameter is not defined for chairman statements which is why the Swedish words in those
        statements get included too.

        Args:
            statement (Statement): a statement to preprocess
            textfile (IO[Any]): a file handle for writing output
            path (Path): path to the file being processed

        Returns:
            Set[str]: a set of unique Finnish words within the statement
        """
        txt = statement.text
        if statement.embedded_statement.text:
            txt = txt.replace("#ch_statement", statement.embedded_statement.text)
        try:
            txt = preprocessor.apply(
                txt, self.recipe.REGEXPS, self.recipe.UNACCEPTED_CHARS, self.recipe.TRANSLATIONS
            )
            textfile.write(" " + txt.lower())
            if "fi" in statement.language:
                return set(txt.split())
        except preprocessor.UnacceptedCharsError as e:
            self.log.debug(f"Error message for {path}:\n {e}")
            self.errors.append(f"UnacceptedCharsError in {path}. See log for debug info.")
        except Exception as e:
            self.log.exception(
                f"Preprocessing failed in {path} in statement beginning at "
                f"'{statement.start_time}' with error message:\n {e}."
            )
            self.errors.append(f"Caught an exception in {path}.")
        return set()
