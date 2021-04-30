"""Test speaker aligining loop."""
from __future__ import annotations  # for difflib.SequenceMatcher type annotation

import csv
import difflib
import json
import logging
from collections import deque
from itertools import islice
from pathlib import Path
from typing import Any
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import pandas as pd
from aalto_asr_preprocessor import preprocessor

from fi_parliament_tools.preprocessing import decode_transcript
from fi_parliament_tools.speakerAligner import IO
from fi_parliament_tools.transcriptParser.data_structures import EmbeddedStatement
from fi_parliament_tools.transcriptParser.data_structures import Statement


def adjust_indices(df: pd.DataFrame, start_idx: int, end_idx: int) -> Tuple[int, int]:
    """Update statement end index if ASR hypothesis does not match transcript.

    The Kaldi alignment may have matched the last words of a statement to untranscribed speech
    following the statement.

    Args:
        df (pd.DataFrame): alignment CTM without silences and UNK tokens
        start_idx (int): current start point for a statement
        end_idx (int): current end point for a statement

    Raises:
        RuntimeError: alignment has failed if start and end indices are the same

    Returns:
        Tuple[int, int]: updated end point for a statement
    """
    if start_idx == end_idx:
        raise RuntimeError("No alignment found!")
    cors = df.iloc[start_idx:end_idx].edit.values == "cor"
    first_cor_idx: int = cors.argmax()
    last_cor_idx: int = cors[::-1].argmax()
    if last_cor_idx > 0:
        last_cor_idx += 1
    return start_idx + first_cor_idx, end_idx - last_cor_idx


def assign_speaker(
    df: pd.DataFrame,
    start_idx: int,
    end_idx: int,
    text: str,
    statement: Union[Statement, EmbeddedStatement],
) -> Tuple[int, int]:
    """Assign speaker to a statement in the aligned CTM.

    Args:
        df (pd.DataFrame): aligned CTM
        start_idx (int): start of the statement in the masked CTM
        end_idx (int): end of the statement in the masked CTM
        text (str): preprocessed statement text
        statement (Union[Statement, EmbeddedStatement]): statement object

    Returns:
        Tuple[int, int]: updated start and end points for next statements
    """
    start_idx = end_idx

    start_idx, end_idx = statement_is_aligned(
        df[["transcript", "edit"]], text.split(), start_idx, statement.language
    )
    if not statement.language == "sv":
        start_idx, end_idx = adjust_indices(df, start_idx, end_idx)
    df.loc[start_idx:end_idx, "speaker"] = statement.firstname + " " + statement.lastname
    df.loc[start_idx:end_idx, "mpid"] = statement.mp_id

    return start_idx, end_idx


def get_segment_speaker(row: pd.Series, main_df: pd.DataFrame, sil_mask: pd.Series) -> int:
    """Determine the speaker ID for a segment or return 0 if a segment has more than one speaker.

    Args:
        row (pd.Series): row in the list of segments
        main_df (pd.DataFrame): aligned CTM with speaker assignments
        sil_mask (pd.Series): hides sil and UNK tokens

    Returns:
        int: MP ID of the segment speaker or 0 if more than one speaker
    """
    shift = row.seg_start_idx - row.word_id
    length = row.seg_end_idx - row.seg_start_idx
    start = row.name[0] + shift
    slice = main_df.mpid.iloc[start : start + length].loc[sil_mask]
    mpids: List[int] = slice.unique()
    mpids.sort()
    if len(mpids) == 2 and 0 in mpids and sum(slice == 0) < 2:
        return mpids[1]
    elif len(mpids) > 1:
        return 0
    return mpids[0]


def form_new_utterance_id(row: pd.Series, session: str) -> str:
    """Form a new utterance id based on the row values.

    Args:
        row (pd.Series): a row from the segments DataFrame
        session (str): session id

    Returns:
        str: new utterance id or empty string if a segment has more than one speaker
    """
    if row.mpid != 0:
        s = int(row.start * 100)
        e = int(row.end * 100)
        return f"{row.mpid:05}-{session}-{s:08}-{e:08}"
    return ""


def statement_is_aligned(
    df: pd.DataFrame, text: List[str], start_idx: int, lang: str, match_limit: int = 20
) -> Tuple[int, int]:
    """Find where the statement text starts and ends in the alignment CTM.

    Args:
        df (pd.DataFrame): alignment CTM
        text (List[str]): statement text to find as a list of words
        start_idx (int): starting point for the search (end of last statement)
        lang (str): handle Swedish and Finnish different
        match_limit (int): the number of words to match in search, defaults to 20

    Raises:
        RuntimeError: raised if no alignment could be found

    Returns:
        Tuple[int, int]: start and end indices of statement text
    """
    remaining = df.iloc[start_idx::]
    masked = remaining[(remaining.transcript != "<eps>") & (remaining.transcript != "<UNK>")]
    matched = min(len(text), match_limit)
    for w in sliding_window(masked.transcript.values):
        diffs = difflib.SequenceMatcher(None, list(w), text[:matched])
        hits = sum(match.size for match in diffs.get_matching_blocks())
        shift = diffs.get_matching_blocks()[0].a
        if hits / matched > 0.75:
            edit_ratios = masked.edit[shift : shift + hits].value_counts(normalize=True)
            if lang == "sv" or ("cor" in edit_ratios and edit_ratios["cor"] > 0.5):
                return masked.index[shift], find_end(masked.transcript[shift:], text)
        if shift == 0:
            shift += matched
        if len(diffs.get_matching_blocks()) < 5:
            return statement_is_aligned(df, text, masked.index[shift], lang)
        break
    raise RuntimeError("No alignment found!")


def find_end(masked: pd.DataFrame, text: List[str]) -> int:
    """Find the last index of the statement text in the transcript column of the alignment CTM.

    Args:
        masked (pd.DataFrame): silence and unk masked transcript
        text (List[str]): statement text as a list of words

    Returns:
        int: last index of the statement
    """
    search_end = min(len(text) + 100, len(masked) - 1)
    diffs = difflib.SequenceMatcher(None, masked.iloc[:search_end].values, text)
    ops = diffs.get_opcodes()
    if ops[-1][0] == "equal":
        return int(masked.index[ops[-1][2]])
    matches = diffs.get_matching_blocks()
    return int(masked.index[next(m.a + m.size for m in matches[::-1] if m.size > 1)])


def sliding_window(
    iterable: Iterable[Any], size: int = 500, step: int = 250, fillvalue: Optional[Any] = None
) -> Iterator[Any]:
    """Form a deque-based sliding window for iterables with variable size and step.

    From: https://stackoverflow.com/a/13408251

    Args:
        iterable (Iterable[Any]): the target of the sliding window
        size (int): size/length of the window, defaults to 300
        step (int): move window forward by step on each iteration, defaults to 150
        fillvalue (Any, optional): padding in the last window (if needed), defaults to None

    Raises:
        ValueError: invalid size/step parameters

    Returns:
        None: return nothing when iteration stops

    Yields:
        Iterator[Any]: current window
    """
    if size < 0 or step < 1:
        raise ValueError
    it = iter(iterable)
    q = deque(islice(it, size), maxlen=size)
    if not q:
        return  # empty iterable or size == 0
    q.extend(fillvalue for _ in range(size - len(q)))  # pad to size
    while True:
        yield iter(q)  # iter() to avoid accidental outside modifications
        try:
            q.append(next(it))
        except StopIteration:  # Python 3.5 pep 479 support
            return
        q.extend(next(it, fillvalue) for _ in range(step - 1))


def rewrite_segments_and_text(
    basepath: Path,
    session: str,
    json_file: str,
    recipe: Any,
    stats: pd.DataFrame,
    log: logging.Logger,
    errors: List[str],
) -> pd.DataFrame:
    """Rewrite files so that only segments with one speaker are included and convert timestamps."""
    with open(json_file, mode="r", encoding="utf-8", newline="") as infile:
        transcript = json.load(infile, object_hook=decode_transcript)
    df = IO.ctm_edits_to_dataframe(f"{basepath}/session-{session}_ctm_edits.segmented")
    df.attrs["session"] = session

    info = df.segment_info.str.extractall(r"start-segment-(\d+)\[start=(\d+),end=(\d+)").astype(int)
    info.rename(columns={0: "seg_num", 1: "seg_start_idx", 2: "seg_end_idx"}, inplace=True)
    info["word_id"] = df.word_id[info.index.get_level_values(None)].values

    segments_df = IO.segments_to_dataframe(f"{basepath}/session-{session}_segments")
    text_df = pd.read_csv(f"{basepath}/session-{session}_text", sep="\n", names=["uttid"])
    split = text_df.uttid.str.split(" ", n=1, expand=True)
    text_df.uttid = split[0]
    text_df = text_df.assign(text=split[1], new_uttid="")

    if len(info) != len(segments_df):
        raise RuntimeError("Different amount of segments in ctm_edits and Kaldi segments files.")

    stat_row = {
        "length": df.session_start.iloc[-1] + df.word_duration.iloc[-1],
        "statements": 0,
        "failed_statements": 0,
        "segments": 0,
        "dropped_segments": 0,
        "segments_len": 0,
        "dropped_len": 0,
    }

    start_idx = end_idx = 0
    for sub in transcript.subsections:
        for statement in sub.statements:
            texts = [statement.text]
            statements = [statement]
            if statement.embedded_statement.text:
                texts = list(statement.text.partition("#ch_statement"))
                texts[1] = statement.embedded_statement.text
                statements = [statement, statement.embedded_statement, statement]
            texts = [
                preprocessor.apply(
                    txt, recipe.REGEXPS, recipe.UNACCEPTED_CHARS, recipe.TRANSLATIONS
                )
                for txt in texts
                if len(txt.strip().split(" ")) > 1
            ]
            stat_row["statements"] += len(texts)
            for txt, statement in zip(texts, statements):
                try:
                    start_idx, end_idx = assign_speaker(df, start_idx, end_idx, txt, statement)
                except RuntimeError as err:
                    stat_row["failed_statements"] += 1
                    msg = f"Cannot align statement {statement} in {session} because '{err}'."
                    errors.append(msg)

    mask = (df.edit != "sil") & (df.edit != "fix")
    segments_df["mpid"] = (
        info.apply(lambda x: get_segment_speaker(x, df, mask), axis=1).astype(int).values
    )
    segments_df["new_uttid"] = segments_df.apply(
        lambda x: form_new_utterance_id(x, df.attrs["session"]), axis=1
    )
    segments_df.recordid = session
    text_df["new_uttid"] = segments_df["new_uttid"]

    dropped_segments = segments_df[segments_df.new_uttid == ""]
    stat_row["segments"] = len(segments_df)
    stat_row["segments_len"] = (segments_df.end - segments_df.start).sum()
    stat_row["dropped_segments"] = len(dropped_segments)
    stat_row["dropped_len"] = (dropped_segments.end - dropped_segments.start).sum()

    stats.loc[f"session-{session}"] = stat_row

    segments_df[segments_df.new_uttid != ""].to_csv(
        f"{basepath}/session-{session}_segments_new",
        sep=" ",
        float_format="%.2f",
        columns=["new_uttid", "recordid", "start", "end"],
        header=False,
        index=False,
    )
    text_df[text_df.new_uttid != ""].to_csv(
        f"{basepath}/session-{session}_text_new",
        sep=" ",
        columns=["new_uttid", "text"],
        header=False,
        index=False,
        quoting=csv.QUOTE_NONE,
        escapechar=" ",
    )
    return stats
