"""Test post-2015 session parsing."""
from dataclasses import asdict
from pathlib import Path
from typing import Any
from typing import Collection
from typing import Dict
from typing import List
from typing import Tuple

import pytest

from fi_parliament_tools.transcriptParser.documents import Session


@pytest.mark.parametrize(
    "session, true_result",
    [
        ((32, 2016), "2016-04-05 13:59:28.087"),
        ((7, 2018), "2018-02-15T16:00:00"),
        ((72, 2019), "2019-11-28T16:00:00"),
    ],
    indirect=["session"],
)
def test_start_time(session: Session, true_result: str) -> None:
    """Test that session start time stamp is correctly parsed."""
    timestamp = session.get_session_start_time()
    assert timestamp == true_result


@pytest.mark.parametrize(
    "session, id, true_title, true_firstname, true_lastname",
    [
        ((1, 2015), 1, "Ikäpuhemies", "Pertti", "Salolainen"),
        ((65, 2017), 4, "Puhemies", "", ""),  # Missing name
        ((7, 2018), 3, "Puhemies", "Paula", "Risikko"),
        ((72, 2019), 2, "Ensimmäinen varapuhemies", "Tuula", "Haatainen"),
    ],
    indirect=["session"],
)
def test_chairman_info(
    session: Session, id: int, true_title: str, true_firstname: str, true_lastname: str
) -> None:
    """Test that chairman info is correctly parsed."""
    [element] = session.xml_transcript.xpath(f"(. //*[local-name() = 'Toimenpide'])[{id}]")
    title, firstname, lastname = session.get_chairman_info(element)
    assert title == true_title
    assert firstname == true_firstname
    assert lastname == true_lastname


@pytest.mark.parametrize(
    "session, id, true_chairman_text",
    [((1, 2015), 17, 0), ((124, 2017), 2, 1), ((72, 2019), 1, 2)],
    indirect=["session", "true_chairman_text"],
)
def test_chairman_text(session: Session, id: int, true_chairman_text: str) -> None:
    """Test that chairman statement is correctly parsed."""
    [element] = session.xml_transcript.xpath(
        f"(. //*[local-name() = 'PuheenjohtajaRepliikki'])[{id}]"
    )
    text = session.get_short_statement_text(element)
    assert text == true_chairman_text


@pytest.mark.parametrize(
    "session, subsection, true_speaker_list",
    [((7, 2018), 3.2, 0), ((108, 2018), 7, 1), ((40, 2020), 3, 2)],
    indirect=["session", "true_speaker_list"],
)
def test_speaker_info(
    session: Session,
    subsection: float,
    true_speaker_list: List[Tuple[int, str, str, str, str]],
) -> None:
    """Test that speaker name and additional information is correctly parsed."""
    elements = session.xml_transcript.xpath(
        f". /*[local-name() = 'Asiakohta'][*[local-name() = 'KohtaNumero' and .='{subsection}']]"
        "//*[local-name() = 'PuheenvuoroToimenpide']/*[local-name() = 'Toimija']"
    )
    assert len(elements) > 0
    for element, speaker in zip(elements, true_speaker_list):
        mp_id, firstname, lastname, party, cabinet_minister = session.get_speaker_info(element)
        assert mp_id == speaker[0]
        assert firstname == speaker[1]
        assert lastname == speaker[2]
        assert party == speaker[3]
        assert cabinet_minister == speaker[4]


@pytest.mark.parametrize(
    "session, true_speaker_text",
    [((18, 2015), 0), ((7, 2018), 1), ((72, 2019), 2)],
    indirect=True,
)
def test_speaker_text(session: Session, true_speaker_text: str) -> None:
    """Test that the speaker statement text is correctly parsed."""
    [element] = session.xml_transcript.xpath("(. //*[local-name() = 'PuheenvuoroOsa'])[1]")
    text = session.get_speaker_statement_text(element)
    assert " ".join(text) == true_speaker_text


@pytest.mark.parametrize(
    "session, true_starttime, true_endtime",
    [
        ((18, 2015), "2015-06-10T14:13:37", "2015-06-10T14:15:43"),
        ((85, 2016), "2016-09-16T13:05:30", "2016-09-16T13:07:43"),
        ((72, 2019), "2019-11-28T16:02:15", "2019-11-28T16:03:26"),
    ],
    indirect=["session"],
)
def test_speaker_statement_timestamps(
    session: Session, true_starttime: str, true_endtime: str
) -> None:
    """Test that the timestamps of the speaker statement are correctly parsed."""
    [element] = session.xml_transcript.xpath(
        "(. //*[local-name() = 'PuheenvuoroToimenpide'])[1]/*[local-name() = 'PuheenvuoroOsa']"
    )
    start_time, end_time = session.get_speaker_statement_timestamps(element)
    assert start_time == true_starttime
    assert end_time == true_endtime


@pytest.mark.parametrize(
    "session, id, true_language",
    [
        ((32, 2016), 3, "fi"),
        ((65, 2017), 42, "sv"),
        ((7, 2018), 54, "sv"),
        ((72, 2019), 27, "sv"),
    ],
    indirect=["session"],
)
def test_language_code(session: Session, id: int, true_language: str) -> None:
    """Test that speaker statement language codes are correctly parsed."""
    [element] = session.xml_transcript.xpath(
        f"(. //*[local-name() = 'PuheenvuoroToimenpide'])[{id}]"
        "/*[local-name() = 'PuheenvuoroOsa'][1]"
    )
    language_code = session.get_language_code(element)
    assert language_code == true_language


@pytest.mark.parametrize(
    "session, subsection, json_test_data",
    [
        ((32, 2016), 4, "tests/data/jsons/session-032-2016-4.json"),
        ((85, 2016), 4, "tests/data/jsons/session-085-2016-4.json"),
        ((70, 2017), 7, "tests/data/jsons/session-070-2017-7.json"),
    ],
    indirect=["session", "json_test_data"],
)
def test_speaker_statements(session: Session, subsection: int, json_test_data: Any) -> None:
    """Test a subsection of a transcript is parsed correctly."""
    elements = session.xml_transcript.xpath(
        f". /*[local-name() = 'Asiakohta'][*[local-name() = 'KohtaNumero' and .='{subsection}']]"
        "//*[local-name() = 'PuheenvuoroToimenpide']"
    )
    assert len(elements) > 0
    statements = [s for e in elements for s in session.compose_speaker_statements(e)]
    for statement, true_statement in zip(statements, json_test_data):
        assert asdict(statement) == true_statement


@pytest.mark.parametrize(
    "session, subsection, true_chairman_statement",
    [((85, 2016), 4, 0), ((65, 2017), 3, 1), ((108, 2018), 6, 2)],
    indirect=["session", "true_chairman_statement"],
)
def test_chairman_statements(
    session: Session,
    subsection: int,
    true_chairman_statement: Dict[str, Collection[str]],
) -> None:
    """Test a subsection of a transcript is parsed correctly."""
    [element] = session.xml_transcript.xpath(
        f". /*[local-name() = 'Asiakohta'][*[local-name() = 'KohtaNumero' and .='{subsection}']]"
        "//*[local-name() = 'Toimenpide']//*[local-name() = 'PuheenjohtajaRepliikki']"
    )
    statement = session.compose_chairman_statement(element)
    assert asdict(statement) == true_chairman_statement


@pytest.mark.parametrize(
    "session, id, embedded_id, true_embedded_statement",
    [
        ((32, 2016), 39, 3, 0),
        ((65, 2017), 5, -1, 1),
        ((108, 2018), 1, 10, 2),
        ((40, 2020), 1, 10, 3),
    ],
    indirect=["session", "true_embedded_statement"],
)
def test_embedded_chairman_statement(
    session: Session, id: int, embedded_id: int, true_embedded_statement: Dict[str, str]
) -> None:
    """Test that chairman statements embedded in speaker statements are found."""
    [element] = session.xml_transcript.xpath(
        f"(. //*[local-name() = 'PuheenvuoroToimenpide'])[{id}]/*[local-name() = 'PuheenvuoroOsa']"
    )
    dummy_main_text = ["", "", "", "", "", "", "", "", "", ""]
    embedded = session.check_embedded_statement(element, dummy_main_text)
    assert asdict(embedded) == true_embedded_statement
    if embedded_id > -1:
        assert dummy_main_text[embedded_id] == "#ch_statement"


@pytest.mark.parametrize(
    "session, true_output_path",
    [
        ((34, 2015), "tests/data/jsons/session-034-2015.json"),
        ((19, 2016), "tests/data/jsons/session-019-2016.json"),
        ((35, 2018), "tests/data/jsons/session-035-2018.json"),
        ((7, 2020), "tests/data/jsons/session-007-2020.json"),
    ],
    indirect=["session"],
)
def test_parse_to_json(session: Session, true_output_path: str, tmp_path: Path) -> None:
    """Test that a session transcript is correctly parsed into a JSON file.

    Args:
        session (Session): parliament plenary session to parse
        true_output_path (str): path to the file used as comparison
        tmp_path (Path): built-in pytest fixture for creating temporary output files
    """
    tmpfile = tmp_path / "tmp_output_test.json"
    session.parse_to_json(tmpfile)
    with open(true_output_path, "r", encoding="utf-8") as true_file:
        assert tmpfile.read_text("utf-8") == true_file.read()
