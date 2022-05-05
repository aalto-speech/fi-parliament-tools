"""Test cases for the command line client in __main__ module."""
import glob
import json
import os
import shutil
from pathlib import Path
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


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


@pytest.fixture
def mock_downloads_requests_get(mocker: MockerFixture) -> MagicMock:
    """Mock returned jsons of the requests.get calls in downloads module."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.downloads.requests.get")
    with open("tests/data/jsons/video_query.json", encoding="utf-8") as infile:
        mock.return_value.__enter__.return_value.json.return_value = json.load(infile)
    return mock


@pytest.fixture
def mock_get_full_table(
    mocker: MockerFixture, query_get_full_table: Tuple[List[List[Optional[str]]], List[str]]
) -> MagicMock:
    """Mock a small table instead of the true big table."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.parsing.query.Query.get_full_table")
    mock.return_value = query_get_full_table
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
        assert "Found 5 transcripts, begin preprocessing." in result.output
        assert "Encountered 3 non-breaking error(s)." in result.output
        assert "Preprocessing output was empty for session-022-2019." in result.output
        assert "Encountered unknown MP in " in result.output
        assert "Finished successfully!" in result.output
        mock_fasttextmodel_load.assert_called_once_with("recipes/lid.176.bin")
        assert mock_fasttextmodel_load.return_value.predict.call_count == 29
        assert mock_mp_table().index.__getitem__().empty.__bool__.call_count == 21
        assert mock_mp_table().index.__getitem__().__getitem__.call_count == 18

        jsondir = f"{workdir}/tests/data/jsons"
        for text in glob.glob("*.text"):
            with open(text, encoding="utf-8") as outf, open(
                f"{jsondir}/{text}", encoding="utf-8"
            ) as truef:
                assert outf.read() + "\n" == truef.read()

        with open("session-007-2020.json", encoding="utf-8") as outf, open(
            f"{jsondir}/session-007-2020.json.updated", encoding="utf-8"
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
@mock.patch("fi_parliament_tools.downloads.atomic_write")
@mock.patch("builtins.open")
@pytest.mark.parametrize(
    "mock_downloads_form_path", ([Path("session-135-2018.mp4"), None],), indirect=True
)
def test_video_download_only(
    mocked_open: MagicMock,
    mocked_atomic_write: MagicMock,
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
        assert "Encountered 0 non-breaking error(s)." in result.output
        assert "Finished successfully!" in result.output
        mocked_open.assert_called_once()
        mocked_atomic_write.assert_called_once()
        mocked_copy.assert_called_once()
        mocked_run.assert_called_once()
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
        assert "Found 0 sessions in file list, begin postprocessing." in result.output
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
        assert "Found 3 sessions in file list, begin postprocessing." in result.output
        assert "Session number and year not in filename:" in result.output
        assert "Finished successfully!" in result.output
        assert "Statistics of the speaker alignment" in result.output


@mock.patch("fi_parliament_tools.mptable.get_data")
@mock.patch("fi_parliament_tools.mptable.pd.DataFrame.set_index")
def test_mptable(
    mocked_set_index: MagicMock, mocked_get_data: MagicMock, runner: CliRunner
) -> None:
    """It successfully runs the mptable client."""
    with runner.isolated_filesystem():
        result = runner.invoke(__main__.main, ["build-mptable"])
        assert "Output is logged to" in result.output
        assert "Begin building MP data table." in result.output
        assert "Fetch all MP data." in result.output
        assert "Parse fetched data." in result.output
        assert "Encountered 0 non-breaking error(s)." in result.output
        mocked_get_data.assert_called_once()
        mocked_set_index.assert_called_once_with("mp_id")
