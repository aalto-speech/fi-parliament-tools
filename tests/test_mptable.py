"""Test building of the MP table."""
from logging import Logger
from typing import List
from unittest import mock
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pytest_mock.plugin import MockerFixture  # type: ignore

from fi_parliament_tools import mptable


@pytest.fixture
def mp_data() -> List[List[str]]:
    """Return dummy MP data for tests."""
    return [
        ["20", "McPerson", "Pat"] + 4 * [""] + 2 * ["<Henkilo><Ammatti/></Henkilo>"],
        ["21", "Another", "A"] + 4 * [""] + 2 * ["<Henkilo></Henkilo>"],
    ]


@pytest.fixture
def mp_tables() -> List[pd.DataFrame]:
    """MP tables for testing table updating."""
    old_table = pd.DataFrame(
        {"firstname": ["Jouko", "Outdated", "Tom"], "lastname": ["Skinnari", "Info", "Packalén"]},
        index=pd.Index([267, 999, 1095], name="mp_id"),
    )
    added_table = pd.DataFrame(
        {
            "firstname": ["Jouko", "Outdated", "Tom", "Eeva"],
            "lastname": ["Skinnari", "Info", "Packalén", "Kalli"],
        },
        index=pd.Index([267, 999, 1095, 1412], name="mp_id"),
    )
    updated_table = pd.DataFrame(
        {
            "firstname": ["Jouko", "Updated", "Tom", "Eeva"],
            "lastname": ["Skinnari", "Info", "Packalén", "Kalli"],
        },
        index=pd.Index([267, 999, 1095, 1412], name="mp_id"),
    )
    return [old_table, added_table, updated_table]


@pytest.fixture
def mock_path_exists(mocker: MockerFixture) -> MagicMock:
    """Mock a path to existence."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.mptable.Path.exists")
    mock.side_effect = [True, False]
    return mock


@pytest.fixture
def mock_mpquery_get_full_table(mocker: MockerFixture) -> MagicMock:
    """Mock MP query's get full table call."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.mptable.MPQuery.get_full_table")
    mock.return_value = ([["102", ""], ["103", ""], ["137", ""], ["945", ""], ["1444", ""]], [])
    return mock


@mock.patch("fi_parliament_tools.mptable.add_new_mps")
@mock.patch("fi_parliament_tools.mptable.pd.read_csv")
@mock.patch("fi_parliament_tools.mptable.parse_mp_data")
@mock.patch("fi_parliament_tools.mptable.get_data")
def test_build_table(
    mocked_get_data: MagicMock,
    mocked_parse: MagicMock,
    mocked_read: MagicMock,
    mocked_add_new: MagicMock,
    mock_path_exists: MagicMock,
    logger: Logger,
) -> None:
    """Test the building of an MP data table with and without an existing table."""
    mptable.build_table(False, False, logger)
    mocked_parse.assert_called_with(mocked_get_data.return_value, False)
    mptable.build_table(True, False, logger)
    assert mocked_get_data.call_count == 2
    assert mock_path_exists.call_count == 2
    mocked_read.assert_called_once_with("generated/mp-table.csv", sep="|", index_col="mp_id")
    mocked_add_new.assert_called_once_with(
        mocked_read.return_value, mocked_parse.return_value, logger, update_old=False
    )
    mocked_parse.assert_called_with(mocked_get_data.return_value, True)
    mocked_add_new().to_csv.assert_called_once_with("generated/mp-table.csv", sep="|")
    mocked_parse().to_csv.assert_called_once_with("generated/mp-table.csv", sep="|")


def test_get_data(mock_mpquery_get_full_table: MagicMock) -> None:
    """Test MP data fetching and filtering."""
    true_data = [["103", ""], ["945", ""], ["1444", ""]]
    data = mptable.get_data()
    assert data == true_data
    mock_mpquery_get_full_table.assert_called_once()


@mock.patch("fi_parliament_tools.mptable.MPInfo.parse")
@mock.patch("fi_parliament_tools.mptable.pd.DataFrame.set_index")
def test_parse_mp_data(
    mocked_set_index: MagicMock, mocked_parse: MagicMock, mp_data: List[List[str]]
) -> None:
    """Test logic in MP data parsing."""
    mptable.parse_mp_data(mp_data)
    mocked_set_index.assert_called_once_with("mp_id")
    assert mocked_parse.call_count == 2


@mock.patch("fi_parliament_tools.mptable.MPInfo.parse")
@mock.patch("fi_parliament_tools.mptable.pd.DataFrame.set_index")
def test_parse_mp_data_english(
    mocked_set_index: MagicMock, mocked_parse: MagicMock, mp_data: List[List[str]]
) -> None:
    """Test logic in MP data parsing when requesting English data."""
    mptable.parse_mp_data(mp_data, get_english=True)
    mocked_set_index.assert_called_once_with("mp_id")
    assert mocked_parse.call_count == 2


@pytest.mark.parametrize(
    "xml, true_result", [("<test><tag/></test>", True), ("<test></test>", False)]
)
def test_contains_empty_tag(xml: str, true_result: bool) -> None:
    """Test empty XML tag named 'tag' is detected."""
    assert mptable.contains_empty_tag("tag", xml) == true_result


def test_add_new_mps(mp_tables: List[pd.DataFrame], logger: Logger) -> None:
    """Test new MPs are added to the MP table."""
    added = mptable.add_new_mps(mp_tables[0], mp_tables[1], logger)
    assert (added == mp_tables[1]).all().all()


def test_add_new_mps_update(mp_tables: List[pd.DataFrame], logger: Logger) -> None:
    """Test new MPs are added to the MP table and old info is updated."""
    updated = mptable.add_new_mps(mp_tables[0], mp_tables[2], logger, update_old=True)
    assert (updated == mp_tables[2]).all().all()
