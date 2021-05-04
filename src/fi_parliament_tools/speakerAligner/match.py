"""Test speaker aligining loop."""
from __future__ import annotations  # for difflib.SequenceMatcher type annotation

import difflib
import json
from collections import deque
from collections import namedtuple
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

from fi_parliament_tools.speakerAligner import IO
from fi_parliament_tools.transcriptParser.data_structures import decode_transcript
from fi_parliament_tools.transcriptParser.data_structures import EmbeddedStatement
from fi_parliament_tools.transcriptParser.data_structures import Statement
from fi_parliament_tools.transcriptParser.data_structures import Transcript


Match = namedtuple("Match", "a b size")
StatementsList = List[Union[Statement, EmbeddedStatement]]


def adjust_indices(df: pd.DataFrame, start_idx: int, end_idx: int) -> Tuple[int, int]:
    """Update statement end index if ASR hypothesis does not match transcript.

    The Kaldi alignment may have matched the last words of a statement to untranscribed speech
    following the statement.

    Args:
        df (pd.DataFrame): alignment CTM without silences and UNK tokens
        start_idx (int): current start point for a statement
        end_idx (int): current end point for a statement

    Raises:
        ValueError: alignment has failed if start and end indices are the same

    Returns:
        Tuple[int, int]: updated end point for a statement
    """
    if start_idx == end_idx:
        raise ValueError("Found segment is of length 0.")
    cors = df.iloc[start_idx:end_idx].edit.values == "cor"
    first_cor_idx: int = cors.argmax()
    last_cor_idx: int = cors[::-1].argmax()
    if last_cor_idx > 0:
        last_cor_idx += 1
    return start_idx + first_cor_idx, end_idx - last_cor_idx


def assign_speaker(
    df: pd.DataFrame, text: str, statement: Union[Statement, EmbeddedStatement]
) -> pd.DataFrame:
    """Assign speaker to a statement in the aligned CTM.

    Args:
        df (pd.DataFrame): aligned CTM
        text (str): preprocessed statement text
        statement (Union[Statement, EmbeddedStatement]): statement object

    Returns:
        pd.DataFrame: updated CTM
    """
    start_idx, end_idx = find_statement(
        df[["transcript", "edit"]], text.split(), statement.language
    )
    if not statement.language == "sv":
        start_idx, end_idx = adjust_indices(df, start_idx, end_idx)
    df.loc[start_idx:end_idx, "speaker"] = statement.firstname + " " + statement.lastname
    df.loc[start_idx:end_idx, "mpid"] = statement.mp_id
    df.loc[start_idx:end_idx, "lang"] = statement.language
    return df


def get_segment_speaker(row: pd.Series, main_df: pd.DataFrame, sil_mask: pd.Series) -> int:
    """Determine the speaker ID of a segment or return -1 if a segment has more than one speaker.

    Args:
        row (pd.Series): row in the list of segments
        main_df (pd.DataFrame): aligned CTM with speaker assignments
        sil_mask (pd.Series): hides sil and UNK tokens

    Returns:
        int: MP ID of the segment speaker or -1 if more than one speaker
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
        return -1
    return mpids[0]


def get_segment_language(row: pd.Series, main_df: pd.DataFrame, sil_mask: pd.Series) -> str:
    """Determine the language of a segment.

    Args:
        row (pd.Series): row in the list of segments
        main_df (pd.DataFrame): aligned CTM with language assignments
        sil_mask (pd.Series): hides sil and UNK tokens

    Returns:
        str: language label of the segment
    """
    shift = row.seg_start_idx - row.word_id
    length = row.seg_end_idx - row.seg_start_idx
    start = row.name[0] + shift
    slice = main_df.lang.iloc[start : start + length].loc[sil_mask]
    langs = " ".join(slice.unique())
    if "fi" in langs and "sv" in langs:
        return "fi+sv"
    elif "sv" in langs:
        return "sv"
    return "fi"


def form_new_utterance_id(row: pd.Series, session: str) -> str:
    """Form a new utterance id based on the row values.

    Args:
        row (pd.Series): a row from the segments DataFrame
        session (str): session id

    Returns:
        str: new utterance id or empty string if a segment has more than one speaker
    """
    if row.mpid > 0:
        s = int(row.start * 100)
        e = int(row.end * 100)
        return f"{row.mpid:05}-{session}-{s:08}-{e:08}"
    return ""


def find_statement(
    df: pd.DataFrame, text: List[str], lang: str, match_limit: int = 30, step: int = 7500
) -> Tuple[int, int]:
    """Find where the statement text starts and ends in the alignment CTM.

    Args:
        df (pd.DataFrame): alignment CTM
        text (List[str]): statement text to find as a list of words
        lang (str): handle Swedish and Finnish different
        match_limit (int): the number of words to match in search, defaults to 30
        step (int): the step size of the sliding window, defaults to 7500.

    Raises:
        ValueError: no alignment could be found

    Returns:
        Tuple[int, int]: start and end indices of statement text
    """
    masked = df[(df.transcript != "<eps>") & (df.transcript != "<UNK>")]
    words_matched = min(len(text), match_limit)
    for i, w in enumerate(sliding_window(masked.transcript.values)):
        start, window = (0, list(w))
        diff = difflib.SequenceMatcher(None, window, text[:words_matched])
        while start < step:
            min_m = min(words_matched, 5)
            match = next((m for m in diff.get_matching_blocks() if m.size >= min_m), Match(0, 0, 0))
            start += match.a
            if match.size > 0:
                s = start + i * step
                edit_ratios = masked.edit[s : s + match.size].value_counts(normalize=True)
                if "sv" in lang or ("cor" in edit_ratios and edit_ratios["cor"] > 0.5):
                    return masked.index[s], find_end_index(masked.transcript[s:], text)
                start += words_matched
                diff.set_seq1(window[start:])
            else:
                break
    raise ValueError("Alignment not found.")


def find_end_index(masked: pd.DataFrame, text: List[str]) -> int:
    """Find the last index of the statement text in the transcript column of the alignment CTM.

    Args:
        masked (pd.DataFrame): silence and unk masked transcript
        text (List[str]): statement text as a list of words

    Raises:
        ValueError: end index not found

    Returns:
        int: last index of the statement
    """
    search_end = min(len(text) + 100, len(masked) - 1)
    diff = difflib.SequenceMatcher(None, masked.iloc[:search_end].values, text)
    ops = diff.get_opcodes()
    if ops[-1][0] == "equal":
        return int(masked.index[ops[-1][2]])
    matches = diff.get_matching_blocks()
    if end_idx := next((m.a + m.size for m in matches[::-1] if m.size > 1), 0):
        return int(masked.index[end_idx])
    raise ValueError("Statement end index not found.")


def sliding_window(
    iterable: Iterable[Any], size: int = 10000, step: int = 7500, fillvalue: Optional[Any] = None
) -> Iterator[Any]:
    """Form a deque-based sliding window for iterables with variable size and step.

    From: https://stackoverflow.com/a/13408251

    Args:
        iterable (Iterable[Any]): the target of the sliding window
        size (int): size/length of the window, defaults to 10000
        step (int): move window forward by step on each iteration, defaults to 7500
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
    errors: List[str],
) -> pd.DataFrame:
    """Rewrite files so that only segments with one speaker are included and convert timestamps."""
    with open(json_file, mode="r", encoding="utf-8", newline="") as infile:
        transcript = json.load(infile, object_hook=decode_transcript)

    kaldictm = IO.KaldiCTMSegmented(f"{basepath}/session-{session}.ctm_edits.segmented")
    df = kaldictm.get_df()
    df.attrs["session"] = session
    kaldisegments = IO.KaldiSegments(f"{basepath}/session-{session}.segments")
    segments_df = kaldisegments.get_df()
    kalditext = IO.KaldiText(f"{basepath}/session-{session}.text")
    text_df = kalditext.get_df()

    info = df.segment_info.str.extractall(r"start-segment-(\d+)\[start=(\d+),end=(\d+)").astype(int)
    info.rename(columns={0: "seg_num", 1: "seg_start_idx", 2: "seg_end_idx"}, inplace=True)
    info["word_id"] = df.word_id[info.index.get_level_values(None)].values

    if len(info) != len(segments_df):
        raise RuntimeError("Different amount of segments in ctm_edits and Kaldi segments files.")

    df, statements, failed = match_speakers_to_ctm(df, transcript, recipe, errors)

    mask = (df.edit != "sil") & (df.edit != "fix")
    segments_df["mpid"] = (
        info.apply(lambda x: get_segment_speaker(x, df, mask), axis=1).astype(int).values
    )
    segments_df["lang"] = (info.apply(lambda x: get_segment_language(x, df, mask), axis=1)).values
    segments_df["new_uttid"] = segments_df.apply(
        lambda x: form_new_utterance_id(x, df.attrs["session"]), axis=1
    )
    segments_df.recordid = session
    kept_segments = (segments_df.new_uttid != "") & (segments_df.lang == "fi")
    text_df[["new_uttid", "lang", "mpid"]] = segments_df[["new_uttid", "lang", "mpid"]]
    kaldisegments.save_df(segments_df[kept_segments])
    kalditext.save_df(text_df[kept_segments])
    kaldisegments.save_df(
        segments_df[~kept_segments],
        ".dropped",
        ["uttid", "recordid", "start", "end", "mpid", "lang"],
    )
    kalditext.save_df(text_df[~kept_segments], ".dropped", ["uttid", "lang", "mpid", "text"])

    dropped_segments = segments_df[~kept_segments]
    stat_row = {
        "length": df.session_start.iloc[-1] + df.word_duration.iloc[-1],
        "statements": statements,
        "failed_statements": failed,
        "segments": len(segments_df),
        "dropped_segments": len(dropped_segments),
        "failed_segments": sum(dropped_segments.mpid == 0),
        "multiple_spk": sum(dropped_segments.mpid == -1),
        "swedish": sum(dropped_segments.lang.str.contains("sv")),
        "segments_len": (segments_df.end - segments_df.start).sum(),
        "dropped_len": (dropped_segments.end - dropped_segments.start).sum(),
    }
    stats.loc[f"session-{session}"] = stat_row
    return stats


def match_speakers_to_ctm(
    df: pd.DataFrame, transcript: Transcript, recipe: Any, errors: List[str]
) -> Tuple[pd.DataFrame, int, int]:
    """Iterate through statements in the transcript and try to find them in the aligned CTM.

    Args:
        df (pd.DataFrame): alignment CTM
        transcript (Transcript): session transcript
        recipe (Any): preprocessing recipe for text
        errors (List[str]): description of all encountered errors

    Returns:
        Tuple[pd.DataFrame, int, int]: updated CTM and counts of total statements and failed ones
    """
    total = failed = 0
    for sub in transcript.subsections:
        for main_statement in sub.statements:
            texts = [main_statement.text]
            statements: StatementsList = [main_statement]
            if main_statement.embedded_statement.text:
                texts = list(main_statement.text.partition("#ch_statement"))
                texts[1] = main_statement.embedded_statement.text
                statements = [main_statement, main_statement.embedded_statement, main_statement]
            texts = [
                preprocessor.apply(
                    txt, recipe.REGEXPS, recipe.UNACCEPTED_CHARS, recipe.TRANSLATIONS
                )
                for txt in texts
                if len(txt.strip().split(" ")) > 1
            ]
            total += len(texts)
            for txt, stmnt in zip(texts, statements):
                try:
                    df = assign_speaker(df, txt, stmnt)
                except (ValueError, RuntimeError) as err:
                    failed += 1
                    msg = f"Cannot align statement {stmnt} in {df.attrs['session']}: {err}"
                    errors.append(msg)
    return df, total, failed
