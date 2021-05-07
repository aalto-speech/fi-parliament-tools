"""Test the matching of speakers to aligned Kaldi CTMs."""
import pandas as pd
import pytest

# from fi_parliament_tools.speakerAligner import match


@pytest.fixture
def test_df() -> pd.DataFrame:
    """Read a customized ctm_edits test file to a pandas DataFrame for testing.

    Returns:
        pd.DataFrame: custom ctm_edits file
    """
    cols = ["word_start", "word_duration", "asr", "transcript", "edit"]
    filename = "tests/data/ctms/custom_test_ctm_edits.segmented"
    return pd.read_csv(filename, sep=" ", usecols=[2, 3, 4, 6, 7], names=cols)
