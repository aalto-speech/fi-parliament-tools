"""Test cases for the __main__, downloads, preprocessing, and postprocessing modules."""
import glob
import importlib
import json
import os
import shutil
from logging import Logger
from pathlib import Path
from typing import Any
from typing import Callable
from typing import List
from typing import Optional
from typing import Tuple
from unittest import mock
from unittest.mock import MagicMock

import pytest
from _pytest.fixtures import SubRequest
from click.testing import CliRunner
from pytest_mock.plugin import MockerFixture  # type: ignore

from fi_parliament_tools import __main__
from fi_parliament_tools.downloads import DownloadPipeline
from fi_parliament_tools.preprocessing import PreprocessingPipeline
from fi_parliament_tools.transcriptParser.data_structures import decode_transcript


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


@pytest.fixture
def load_recipe() -> Callable[[str], Any]:
    """Load a recipe module for testing purposes."""

    def _load_recipe(recipe_path: str) -> Any:
        if spec := importlib.util.spec_from_file_location("recipe", recipe_path):
            recipe = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(recipe)  # type: ignore
            return recipe

    return _load_recipe


@pytest.fixture
def tmpfile(tmp_path: Path) -> Path:
    """Create a file in the tmp directory."""
    return tmp_path / "tmp_output.txt"


@pytest.fixture
def transcript() -> Any:
    """Read the dummy transcript from a json."""
    input_json = open(
        "tests/data/jsons/preprocessing_test_sample.json", "r", encoding="utf-8", newline=""
    )
    yield json.load(input_json, object_hook=decode_transcript)
    input_json.close()


@pytest.fixture
def download_pipeline(logger: Logger) -> DownloadPipeline:
    """Initialize DownloadPipeline."""
    pipeline = DownloadPipeline(logger)
    return pipeline


@pytest.fixture
def preprocess_pipeline(logger: Logger, mocker: MockerFixture) -> PreprocessingPipeline:
    """Initialize PreprocessingPipeline with mocked LID model and MP table."""
    mocker.patch("fi_parliament_tools.preprocessing.fasttext.load_model")
    mocker.patch("fi_parliament_tools.preprocessing.pd.read_csv")
    pipeline = PreprocessingPipeline(logger, [], "lid_dummy", "mptable_dummy", "recipe_dummy")
    return pipeline


@pytest.fixture
def mock_downloads_requests_get(mocker: MockerFixture) -> MagicMock:
    """Mock returned jsons of the requests.get calls in downloads module."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.downloads.requests.get")
    with open("tests/data/jsons/video_query.json", "r", encoding="utf-8") as infile:
        mock.return_value.__enter__.return_value.json.return_value = json.load(infile)
    return mock


@pytest.fixture
def mock_get_full_table(
    mocker: MockerFixture, query_get_full_table: Tuple[List[List[Optional[str]]], List[str]]
) -> MagicMock:
    """Mock a small table instead of the true big table."""
    mock: MagicMock = mocker.patch(
        "fi_parliament_tools.transcriptParser.query.Query.get_full_table"
    )
    mock.return_value = query_get_full_table
    return mock


@pytest.fixture
def mock_downloads_path(mocker: MockerFixture) -> MagicMock:
    """Mock path formed in form_path of downloads module."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.downloads.Path")
    mock.return_value.resolve.return_value.__str__.return_value = "tests/testing.test"
    mock.return_value.resolve.return_value.exists.side_effect = [False, True]
    return mock


@pytest.fixture
def mock_subprocess_run(mocker: MockerFixture) -> MagicMock:
    """Trigger an error once in a subprocess.run call."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.downloads.subprocess.run")
    mock.side_effect = [ValueError("Wav extraction failure."), None]
    return mock


@pytest.fixture
def mock_shutil_copyfileobj(mocker: MockerFixture) -> MagicMock:
    """Trigger an error once in a shutil.copyfileobj call."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.downloads.shutil.copyfileobj")
    mock.side_effect = [None, shutil.Error("Video download failure.")]
    return mock


@pytest.fixture
def mock_downloads_form_path(request: SubRequest, mocker: MockerFixture) -> MagicMock:
    """Mock path formed in form_path of downloads module."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.downloads.DownloadPipeline.form_path")
    mock.side_effect = request.param
    return mock


@pytest.fixture
def mock_vaskiquery(request: SubRequest, mocker: MockerFixture) -> MagicMock:
    """Mock a VaskiQuery for the downloads module."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.downloads.VaskiQuery")
    mock.return_value.get_xml.side_effect = request.param
    return mock


@pytest.fixture
def mock_fasttextmodel_load(mocker: MockerFixture) -> MagicMock:
    """Mock FastTextModel loading from a binary file."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.preprocessing.fasttext.load_model")
    mock.return_value.predict.return_value = (("__label__fi", "__label__et"), None)
    return mock


@pytest.fixture
def mock_mp_table(mocker: MockerFixture) -> MagicMock:
    """Mock MP table loading and operations."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.preprocessing.pd.read_csv")
    mock().index.__getitem__().empty.__bool__.side_effect = 18 * [False] + 3 * [True]
    mock().index.__getitem__().__getitem__.side_effect = 5 * [414] + 9 * [1148] + 4 * [809]
    return mock


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


def test_main_succeeds(runner: CliRunner) -> None:
    """It exits with a status code of zero."""
    result = runner.invoke(__main__.main)
    assert result.exit_code == 0


def test_preprocessor(
    mock_fasttextmodel_load: MagicMock, mock_mp_table: MagicMock, runner: CliRunner
) -> None:
    """It successfully preprocesses the three files given the list file."""
    workdir = os.getcwd()
    with runner.isolated_filesystem():
        transcript_file = Path(f"{workdir}/tests/data/transcripts_for_preprocessing_tests.list")
        for json_file in transcript_file.read_text("utf-8").splitlines():
            shutil.copy(f"{workdir}/{json_file}", ".")

        Path("recipes").mkdir(parents=True, exist_ok=True)
        Path("recipes/lid.176.bin").touch()
        Path("recipes/mp-table.csv").touch()
        shutil.copy(f"{workdir}/recipes/words_elative.txt", "recipes/words_elative.txt")

        with open("transcript.list", "w", encoding="utf-8") as outfile:
            for transcript in sorted(glob.glob("*.json")):
                outfile.write(transcript + "\n")

        result = runner.invoke(
            __main__.main,
            [
                "preprocess",
                "transcript.list",
                "recipes/lid.176.bin",
                "recipes/mp-table.csv",
                f"{workdir}/recipes/parl_to_kaldi_text.py",
            ],
        )
        assert result.exit_code == 0
        assert "Output is logged to" in result.output
        assert "Got 5 transcripts, begin preprocessing." in result.output
        assert "Encountered 4 non-breaking error(s)." in result.output
        assert "Preprocessing output was empty for session-022-2019." in result.output
        assert "Encountered unknown MP in " in result.output
        assert "Finished successfully!" in result.output
        mock_fasttextmodel_load.assert_called_once_with("recipes/lid.176.bin")
        assert mock_fasttextmodel_load.return_value.predict.call_count == 29
        assert mock_mp_table().index.__getitem__().empty.__bool__.call_count == 21
        assert mock_mp_table().index.__getitem__().__getitem__.call_count == 18

        for text in glob.glob("*.text"):
            with open(text, "r", encoding="utf-8") as outf, open(
                f"{workdir}/tests/data/jsons/{text}", "r", encoding="utf-8"
            ) as truef:
                assert outf.read() + "\n" == truef.read()


def test_preprocessor_with_bad_recipe_file(runner: CliRunner) -> None:
    """It exits if recipe file is not a python file."""
    workdir = os.getcwd()
    with runner.isolated_filesystem():
        with open("transcript.list", "w", encoding="utf-8") as outfile:
            outfile.write("dummy.json\n")

        Path("lid.176.bin").touch()
        Path("mp-table.csv").touch()

        result = runner.invoke(
            __main__.main,
            [
                "preprocess",
                "transcript.list",
                "lid.176.bin",
                "mp-table.csv",
                f"{workdir}/recipes/swedish_words.txt",
            ],
        )
        assert result.exit_code == 1
        assert "Failed to import recipe" in result.output
        assert "is it a python file?" in result.output


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
        words = preprocess_pipeline.preprocess_statement(mock_statement, tmp_out)

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
        words = preprocess_pipeline.preprocess_statement(mock_statement, tmp_out)

    assert f"Caught an exception in {tmpfile}." == preprocess_pipeline.errors[0]
    assert words == set()


def test_download_limiting_options(runner: CliRunner) -> None:
    """Check that '-v' and '-t' options work and that missing end options are handled correctly."""
    with runner.isolated_filesystem():
        result = runner.invoke(
            __main__.main,
            ["download", "-v", "-t"],
        )
        assert "Output is logged to" in result.output
        assert "No end date or session given, will download sessions up to" in result.output
        assert "Encountered 0 non-breaking error(s)." in result.output
        assert "Finished successfully!" in result.output


@mock.patch("fi_parliament_tools.downloads.subprocess.run")
@mock.patch("fi_parliament_tools.downloads.shutil.copyfileobj")
@mock.patch("builtins.open")
@pytest.mark.parametrize(
    "mock_downloads_form_path", ([Path("session-135-2018.mp4"), None],), indirect=True
)
def test_download_videos(
    mocked_open: MagicMock,
    mocked_copy: MagicMock,
    mocked_run: MagicMock,
    mock_downloads_requests_get: MagicMock,
    mock_downloads_form_path: MagicMock,
    runner: CliRunner,
) -> None:
    """It successfully downloads the videos between given dates."""
    with runner.isolated_filesystem():
        result = runner.invoke(
            __main__.main,
            ["download", "-v", "--start-date", "2018-12-20", "--end-date", "2018-12-22"],
        )
        assert "Output is logged to" in result.output
        assert "Found 2 videos, proceed to download videos and extract audio." in result.output
        assert "Encountered 0 non-breaking error(s)." in result.output
        assert "Finished successfully!" in result.output
        assert mocked_open.call_count == 2  # 1 x logger, 1 x video download
        assert mocked_copy.call_count == 1
        assert mocked_run.call_count == 1
        assert mock_downloads_requests_get.call_count == 2
        assert mock_downloads_form_path.call_count == 2


@mock.patch("fi_parliament_tools.downloads.etree")
@mock.patch("fi_parliament_tools.downloads.Session")
@pytest.mark.parametrize(
    "mock_downloads_form_path, mock_vaskiquery",
    (
        [
            [
                Path("session-135-2018.json"),
                Path("session-136-2018.json"),
                Path("session-137-2018.json"),
            ],
            ["dummy", "dummy2", "dummy3"],
        ],
    ),
    indirect=True,
)
def test_download_transcripts(
    mocked_session: MagicMock,
    mocked_etree: MagicMock,
    mock_get_full_table: MagicMock,
    mock_downloads_form_path: MagicMock,
    mock_vaskiquery: MagicMock,
    runner: CliRunner,
) -> None:
    """It successfully downloads the given transcript range."""
    with runner.isolated_filesystem():
        result = runner.invoke(
            __main__.main,
            ["download", "-t", "--start-session", "135/2018", "--end-session", "137/2018"],
        )

        assert "Output is logged to" in result.output
        assert "Found 3 transcripts, proceed to download transcripts." in result.output
        assert "Encountered 0 non-breaking error(s)." in result.output
        assert "Finished successfully!" in result.output
        assert mocked_session.call_count == 3
        assert len(mocked_etree.method_calls) == 6
        assert mock_vaskiquery.call_count == 3
        mock_get_full_table.assert_called_once()
        assert mock_downloads_form_path.call_count == 3


def test_downloads_form_path(
    mock_downloads_path: MagicMock,
    download_pipeline: DownloadPipeline,
    runner: CliRunner,
) -> None:
    """Check path forming separately."""
    with runner.isolated_filesystem():
        assert str(download_pipeline.form_path(0, 0, "test")) == "tests/testing.test"
        assert len(download_pipeline.errors) == 0
        mock_downloads_path.assert_called_once()

        assert download_pipeline.form_path(0, 0, "test") is None
        assert download_pipeline.errors[0] == "File tests/testing.test exists, will not overwrite."
        assert mock_downloads_path.call_count == 2


@mock.patch("builtins.open")
@pytest.mark.parametrize(
    "mock_downloads_form_path",
    ([Path("session-135-2018.mp4"), Path("session-136-2018.mp4")],),
    indirect=True,
)
def test_video_download_exceptions(
    mocked_open: MagicMock,
    mock_subprocess_run: MagicMock,
    mock_shutil_copyfileobj: MagicMock,
    mock_downloads_requests_get: MagicMock,
    mock_downloads_form_path: MagicMock,
    runner: CliRunner,
) -> None:
    """Test the exception branches in the video download functions."""
    with runner.isolated_filesystem():
        result = runner.invoke(
            __main__.main,
            [
                "download",
                "-v",
                "--start-date",
                "2018-12-20",
                "--end-date",
                "2018-12-22",
                "--start-session",
                "",
            ],
        )
        assert "Output is logged to" in result.output
        assert "Found 2 videos, proceed to download videos and extract audio." in result.output
        assert "Encountered 2 non-breaking error(s)." in result.output
        assert "Wav extraction failed for video session-135-2018.mp4." in result.output
        assert "Video download failed for session-136-2018.mp4" in result.output
        assert "Finished successfully!" in result.output
        assert mocked_open.call_count == 3  # 1 x logger, 2 x video download
        assert mock_subprocess_run.call_count == 2
        assert mock_shutil_copyfileobj.call_count == 2
        assert mock_downloads_requests_get.call_count == 3
        assert mock_downloads_form_path.call_count == 2


@mock.patch("fi_parliament_tools.downloads.etree")
@mock.patch("fi_parliament_tools.downloads.Session")
@pytest.mark.parametrize(
    "mock_downloads_form_path, mock_vaskiquery",
    (
        [
            [Path("session-135-2018.json"), Path("session-136-2018.json")],
            ["dummy", None],
        ],
    ),
    indirect=True,
)
def test_transcript_download_error(
    mocked_session: MagicMock,
    mocked_etree: MagicMock,
    mock_get_full_table: MagicMock,
    mock_downloads_form_path: MagicMock,
    mock_vaskiquery: MagicMock,
    runner: CliRunner,
) -> None:
    """It successfully downloads the given transcript range."""
    with runner.isolated_filesystem():
        result = runner.invoke(
            __main__.main,
            ["download", "-t", "--start-session", "135/2018", "--end-session", "136/2018"],
        )

        assert "Output is logged to" in result.output
        assert "Found 2 transcripts, proceed to download transcripts." in result.output
        assert "Encountered 1 non-breaking error(s)." in result.output
        assert "XML for transcript 136/2018 is not found." in result.output
        assert "Finished successfully!" in result.output
        assert mocked_session.call_count == 1
        assert mock_vaskiquery.call_count == 2
        mock_get_full_table.assert_called_once()
        assert len(mocked_etree.method_calls) == 2
        assert mock_downloads_form_path.call_count == 2


def test_postprocessor_without_input(runner: CliRunner) -> None:
    """It exits cleanly when no files to postprocess given."""
    workdir = os.getcwd()
    with runner.isolated_filesystem():
        Path("recipes").mkdir(parents=True, exist_ok=True)
        shutil.copy(f"{workdir}/recipes/words_elative.txt", "recipes/words_elative.txt")

        with open("ctms.list", "w", encoding="utf-8") as outfile:
            outfile.write("\n")

        result = runner.invoke(
            __main__.main,
            [
                "postprocess",
                "ctms.list",
                f"{workdir}/recipes/parl_to_kaldi_text.py",
            ],
        )
        assert result.exit_code == 0
        assert "Output is logged to" in result.output
        assert "Found 0 sessions in file list, proceed to postprocessing." in result.output
        assert "Finished successfully!" in result.output


def test_postprocessor_with_bad_recipe_file(runner: CliRunner) -> None:
    """It exits if recipe file is not a python file."""
    workdir = os.getcwd()
    with runner.isolated_filesystem():
        with open("ctms.list", "w", encoding="utf-8") as outfile:
            outfile.write("\n")

        result = runner.invoke(
            __main__.main,
            [
                "postprocess",
                "ctms.list",
                f"{workdir}/recipes/swedish_words.txt",
            ],
        )
        assert result.exit_code == 1


def test_postprocessor(runner: CliRunner) -> None:
    """It successfully postprocesses the files given the list file."""
    workdir = os.getcwd()
    session = "session-019-2016"
    with runner.isolated_filesystem():
        for kaldi_file in glob.glob(f"{workdir}/tests/data/ctms/*"):
            shutil.copy(kaldi_file, ".")

        Path("corpus/2016").mkdir(parents=True, exist_ok=True)
        shutil.copy(f"{workdir}/tests/data/jsons/{session}.json", f"corpus/2016/{session}.json")

        Path("recipes").mkdir(parents=True, exist_ok=True)
        shutil.copy(f"{workdir}/recipes/words_elative.txt", "recipes/words_elative.txt")

        with open("ctms.list", "w", encoding="utf-8") as outfile:
            for ctm in glob.glob("*.ctm_edits.segmented"):
                outfile.write(ctm + "\n")

        result = runner.invoke(
            __main__.main,
            [
                "postprocess",
                "ctms.list",
                f"{workdir}/recipes/parl_to_kaldi_text.py",
            ],
        )
        assert result.exit_code == 0
        assert "Output is logged to" in result.output
        assert "Found 4 sessions in file list, proceed to postprocessing." in result.output
        assert "Finished successfully!" in result.output
        assert "Statistics of the speaker alignment" in result.output


@mock.patch("fi_parliament_tools.mptable.get_data")
@mock.patch("fi_parliament_tools.mptable.pd.DataFrame.set_index")
def test_mptable(
    mocked_get_data: MagicMock, mocked_set_index: MagicMock, runner: CliRunner
) -> None:
    """It successfully runs the mptable client."""
    with runner.isolated_filesystem():
        result = runner.invoke(__main__.main, ["build-mptable"])
        assert "Output is logged to" in result.output
        assert "Begin building MP data table." in result.output
        assert "Fetch all MP data." in result.output
        assert "Parse fetched data." in result.output
        assert "Encountered 0 non-breaking error(s)." in result.output
