"""Label segments with language and speaker by matching original transcript to CTM."""
from __future__ import annotations  # for difflib.SequenceMatcher type annotation

import difflib
from collections import deque
from collections import namedtuple
from itertools import islice
from typing import Any
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import pandas as pd
from aalto_asr_preprocessor import preprocessor

from fi_parliament_tools.transcriptMatcher.IO import KaldiCTMSegmented
from fi_parliament_tools.transcriptMatcher.IO import KaldiSegments
from fi_parliament_tools.transcriptMatcher.IO import KaldiText
from fi_parliament_tools.transcriptParser.data_structures import EmbeddedStatement
from fi_parliament_tools.transcriptParser.data_structures import Statement
from fi_parliament_tools.transcriptParser.data_structures import Transcript

Match = namedtuple("Match", "a b size")
StatementsList = List[Union[Statement, EmbeddedStatement]]


def label_segments(
    transcript: Transcript,
    ctm: KaldiCTMSegmented,
    segments: KaldiSegments,
    kalditext: KaldiText,
    recipe: Any,
    errors: List[str],
) -> Tuple[KaldiSegments, KaldiText]:
    """Assign language and speakers to each segment and corresponding text transcript.

    Args:
        transcript (Transcript): original transcript
        ctm (KaldiCTMSegmented): Kaldi ctm_edits.segmented file
        segments (KaldiSegments): Kaldi segments file
        kalditext (KaldiText): Kaldi text file
        recipe (Any): preprocessing recipe for text
        errors (List[str]): description of all encountered errors

    Returns:
        Tuple[KaldiSegments, KaldiText]: matched
    """
    ctm.df = match_ctm_to_transcript(ctm.df, transcript, recipe, errors)
    info = parse_segment_info(ctm.df)
    segments.df = get_labels(ctm.df, segments.df, info)
    kalditext.df[["new_uttid", "lang", "mpid"]] = segments.df[["new_uttid", "lang", "mpid"]]
    return segments, kalditext


def match_ctm_to_transcript(
    df: pd.DataFrame, transcript: Transcript, recipe: Any, errors: List[str]
) -> pd.DataFrame:
    """Iterate through statements in the transcript and try to find them in the aligned CTM.

    Args:
        df (pd.DataFrame): alignment CTM
        transcript (Transcript): session transcript
        recipe (Any): preprocessing recipe for text
        errors (List[str]): description of all encountered errors

    Returns:
        pd.DataFrame: updated CTM
    """
    df.attrs["statements"] = df.attrs["failed"] = 0
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
            df.attrs["statements"] += len(texts)
            for txt, stmnt in zip(texts, statements):
                try:
                    df = assign_speaker(df, txt, stmnt)
                except (ValueError, RuntimeError) as err:
                    df.attrs["failed"] += 1
                    msg = f"Cannot align statement {stmnt} in {df.attrs['session']}: {err}"
                    errors.append(msg)
    return df


def adjust_indices(df: pd.DataFrame, start_idx: int, end_idx: int) -> Tuple[int, int]:
    """Update statement start and end indices if ASR hypothesis does not match transcript.

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
    if "sv" not in statement.language:
        start_idx, end_idx = adjust_indices(df, start_idx, end_idx)
    df.loc[start_idx:end_idx, "speaker"] = statement.firstname + " " + statement.lastname
    df.loc[start_idx:end_idx, "mpid"] = statement.mp_id
    df.loc[start_idx:end_idx, "lang"] = statement.language
    return df


def find_statement(
    df: pd.DataFrame,
    text: List[str],
    lang: str,
    match_limit: int = 30,
    size: int = 10000,
    step: int = 7500,
) -> Tuple[int, int]:
    """Find where the statement text starts and ends in the alignment CTM.

    Args:
        df (pd.DataFrame): alignment CTM
        text (List[str]): statement text to find as a list of words
        lang (str): handle Swedish and Finnish different
        match_limit (int): the number of words to match in search, defaults to 30
        size (int): the size of the sliding window, defaults to 10 000
        step (int): the step size of the sliding window, defaults to 7500

    Raises:
        ValueError: no alignment could be found

    Returns:
        Tuple[int, int]: start and end indices of statement text
    """
    masked = df[(df.transcript != "<eps>") & (df.transcript != "<UNK>")]
    words_matched = min(len(text), match_limit)
    for i, w in enumerate(sliding_window(masked.transcript.values, size=size, step=step)):
        start, window = (0, list(w))
        diff = difflib.SequenceMatcher(None, window, text[:words_matched])
        while start < step:
            min_m = min(words_matched, 5)
            match = next((m for m in diff.get_matching_blocks() if m.size >= min_m), Match(0, 0, 0))
            start += match.a
            if match.size <= 0:
                break
            else:
                s = start + i * step
                edit_ratios = masked.edit[s : s + match.size].value_counts(normalize=True)
                if "sv" in lang or ("cor" in edit_ratios and edit_ratios["cor"] > 0.5):
                    return masked.index[s], find_end_index(masked.transcript[s:], text)
                start += words_matched
                diff.set_seq1(window[start:])
    raise ValueError("Alignment not found.")


def find_end_index(masked: pd.DataFrame, text: List[str], added_range: int = 100) -> int:
    """Find the last index of the statement text in the transcript column of the alignment CTM.

    Args:
        masked (pd.DataFrame): silence and unk masked transcript
        text (List[str]): statement text as a list of words
        added_range (int): search the word up to the added range, defaults to 100

    Raises:
        ValueError: end index not found

    Returns:
        int: last index of the statement
    """
    search_end = min(len(text) + added_range, len(masked) - 1)
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


def parse_segment_info(df: pd.DataFrame) -> pd.DataFrame:
    """Get segment id, start index and end index from the segment info column.

    Args:
        df (pd.DataFrame): alignment CTM

    Returns:
        pd.DataFrame: parsed segment info
    """
    info = df.segment_info.str.extractall(r"start-segment-(\d+)\[start=(\d+),end=(\d+)").astype(int)
    info.rename(columns={0: "seg_num", 1: "seg_start_idx", 2: "seg_end_idx"}, inplace=True)
    info["word_id"] = df.word_id[info.index.get_level_values(None)].values
    return info


def get_labels(df: pd.DataFrame, segments_df: pd.DataFrame, info: pd.DataFrame) -> pd.DataFrame:
    """Get speaker and language labels for segments and form new utterance ids.

    Args:
        df (pd.DataFrame): alignment CTM
        segments_df (pd.DataFrame): Kaldi segments file
        info (pd.DataFrame): contains segment id, segment start and end word indices

    Returns:
        pd.DataFrame: updated segments file
    """
    mask = (df.edit != "sil") & (df.edit != "fix")
    segments_df["mpid"] = (
        info.apply(lambda x: get_segment_speaker(x, df, mask), axis=1).astype(int).values
    )
    segments_df["lang"] = (info.apply(lambda x: get_segment_language(x, df, mask), axis=1)).values
    segments_df["new_uttid"] = segments_df.apply(
        lambda x: form_new_utterance_id(x, df.attrs["session"]), axis=1
    )
    segments_df.recordid = df.attrs["session"]
    return segments_df


def get_segment_speaker(row: pd.Series, main_df: pd.DataFrame, sil_mask: pd.Series) -> int:
    """Determine the speaker id of a segment or return -1 if a segment has more than one speaker.

    Args:
        row (pd.Series): row in the list of segments
        main_df (pd.DataFrame): aligned CTM with speaker assignments
        sil_mask (pd.Series): hides sil and UNK tokens

    Returns:
        int: MP id of the segment speaker or -1 if more than one speaker
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

    The variable row.name corresponds to the index in the main_df where the segment was defined.

    Args:
        row (pd.Series): row in the segment info DataFrame
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
    """Form a new utterance id based on the row values if the segment has only one speaker.

    MP id can take three values:
        - `mpid > 0` -> valid MP id
        - `mpid == 0` -> speaker matching failed or no speaker
        - `mpid == -1` -> multiple speakers

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
