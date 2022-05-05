"""Test cases for the preprocessing module."""
from logging import Logger
from pathlib import Path
from typing import Any
from typing import Callable
from unittest.mock import MagicMock

import pytest
from pytest_mock.plugin import MockerFixture  # type: ignore

from fi_parliament_tools.preprocessing import PreprocessingPipeline


@pytest.fixture
def preprocess_pipeline(logger: Logger, mocker: MockerFixture) -> PreprocessingPipeline:
    """Initialize PreprocessingPipeline with mocked LID model and MP table."""
    mocker.patch("fi_parliament_tools.preprocessing.fasttext.load_model")
    mocker.patch("fi_parliament_tools.preprocessing.pd.read_csv")
    pipeline = PreprocessingPipeline(logger, [], "lid_dummy", "mptable_dummy", "recipe_dummy")
    return pipeline


@pytest.fixture
def mock_statement(mocker: MockerFixture) -> MagicMock:
    """Mock Statement object for the preprocessing module."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.preprocessing.Statement")
    mock.text = (
        "This text is used to test exceptions in preprocessor code. To include a character "
        "that the simple test recipe cannot process, let's say greetings in German: Schöne Grüße!"
    )
    mock.embedded_statement.text = ""
    return mock


def test_determine_language_label(
    preprocess_pipeline: PreprocessingPipeline, mock_statement: MagicMock
) -> None:
    """It labels text as Finnish, Swedish, or both."""
    preprocess_pipeline.lid.predict.side_effect = [
        (("__label__fi", "__label__et"), None),
        (("__label__fi", "__label__sv"), None),
        (("__label__en", "__label__sv"), None),
    ]
    true_labels = ["fi.p", "fi+sv.p", "sv.p"]
    for true_label in true_labels:
        label = preprocess_pipeline.determine_language_label(mock_statement)
        assert label == true_label


def test_preprocessor_unaccepted_chars_capture(
    preprocess_pipeline: PreprocessingPipeline,
    load_recipe: Callable[[str], Any],
    mock_statement: MagicMock,
    tmpfile: Path,
) -> None:
    """Ensure UnacceptedCharsError is captured, logged and recovered from."""
    preprocess_pipeline.recipe = load_recipe("tests/data/simple_recipe.py")
    with open(tmpfile, "w", encoding="utf-8") as tmp_out:
        words = preprocess_pipeline.preprocess_statement(mock_statement, tmp_out, tmpfile)

    assert (
        f"UnacceptedCharsError in {tmpfile}. See log for debug info."
        == preprocess_pipeline.errors[0]
    )
    assert words == set()


def test_preprocessor_exception(
    preprocess_pipeline: PreprocessingPipeline,
    load_recipe: Callable[[str], Any],
    mock_statement: MagicMock,
    tmpfile: Path,
) -> None:
    """Ensure Exception is captured, logged and recovered from."""
    preprocess_pipeline.recipe = load_recipe("tests/data/faulty_recipe.py")
    with open(tmpfile, "w", encoding="utf-8") as tmp_out:
        words = preprocess_pipeline.preprocess_statement(mock_statement, tmp_out, tmpfile)

    assert f"Caught an exception in {tmpfile}." == preprocess_pipeline.errors[0]
    assert words == set()
