"""Test post-2015 session parsing."""
from dataclasses import asdict
from typing import Any
from typing import Collection
from typing import Dict
from typing import List
from typing import Tuple
from unittest.mock import MagicMock

import pytest
from _pytest.fixtures import SubRequest
from pytest_mock.plugin import MockerFixture  # type: ignore

from fi_parliament_tools.parsing.data_structures import MP
from fi_parliament_tools.parsing.data_structures import Transcript
from fi_parliament_tools.parsing.documents import MPInfo
from fi_parliament_tools.parsing.documents import Session


@pytest.fixture
def mock_session_start_time(request: SubRequest, mocker: MockerFixture) -> MagicMock:
    """Mock SessionQuery.get_session_start_time call."""
    mock: MagicMock = mocker.patch("fi_parliament_tools.parsing.documents.SessionQuery")
    mock.return_value.get_session_start_time.return_value = request.param
    return mock


@pytest.mark.parametrize(
    "session, mock_session_start_time, true_result",
    [
        ((32, 2016), "2016-04-05 13:59:28.087", "2016-04-05 13:59:28.087"),
        ((7, 2018), "", "2018-02-15T16:00:00"),
        ((72, 2019), "", "2019-11-28T16:00:00"),
    ],
    indirect=["session", "mock_session_start_time"],
)
def test_start_time(session: Session, mock_session_start_time: MagicMock, true_result: str) -> None:
    """Test that session start time stamp is correctly parsed."""
    timestamp = session.get_session_start()
    assert timestamp == true_result
    mock_session_start_time.assert_called_once_with(session.query_key)
    mock_session_start_time.return_value.get_session_start_time.assert_called_once()


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
    "session, transcript",
    [
        ((7, 2020), "tests/data/jsons/session-007-2020.json"),
        ((19, 2016), "tests/data/jsons/session-019-2016.json"),
        ((34, 2015), "tests/data/jsons/session-034-2015.json"),
        ((35, 2018), "tests/data/jsons/session-035-2018.json"),
        ((130, 2017), "tests/data/jsons/session-130-2017.json"),
        ((141, 2017), "tests/data/jsons/session-141-2017.json"),
    ],
    indirect=True,
)
def test_parse(session: Session, transcript: Transcript) -> None:
    """Test that a session transcript is correctly parsed into a Transcript object.

    Args:
        session (Session): parliament plenary session to parse
        transcript (Transcript): the correct result for comparison
    """
    parsed_session = session.parse()
    assert parsed_session == transcript


@pytest.mark.parametrize(
    "mpinfo, true_gender",
    [
        ("tests/data/xmls/ahde.xml", "o"),
        ("tests/data/xmls/kilpi.xml", "m"),
        ("tests/data/xmls/rehn-kivi.xml", "f"),
        ("tests/data/xmls/suomela.xml", "f"),
    ],
    indirect=["mpinfo"],
)
def test_get_gender(mpinfo: MPInfo, true_gender: str) -> None:
    """Test that gender is correctly parsed from the XML."""
    gender = mpinfo.get_gender()
    assert gender == true_gender


@pytest.mark.parametrize(
    "mpinfo, true_language",
    [
        ("tests/data/xmls/ahde.xml", "fi"),
        ("tests/data/xmls/kilpi.xml", "fi"),
        ("tests/data/xmls/rehn-kivi.xml", "sv"),
        ("tests/data/xmls/suomela.xml", "fi"),
    ],
    indirect=["mpinfo"],
)
def test_get_language(mpinfo: MPInfo, true_language: str) -> None:
    """Test that language is correctly parsed from the XML."""
    language = mpinfo.get_language()
    assert language == true_language


@pytest.mark.parametrize(
    "mpinfo, true_birthyear",
    [
        ("tests/data/xmls/ahde.xml", 1945),
        ("tests/data/xmls/kilpi.xml", 1969),
        ("tests/data/xmls/rehn-kivi.xml", 1956),
        ("tests/data/xmls/suomela.xml", 1994),
    ],
    indirect=["mpinfo"],
)
def test_get_birthyear(mpinfo: MPInfo, true_birthyear: int) -> None:
    """Test that birth year is correctly parsed from the XML."""
    birthyear = mpinfo.get_birthyear()
    assert birthyear == true_birthyear


@pytest.mark.parametrize(
    "mpinfo, true_party",
    [
        ("tests/data/xmls/ahde.xml", "Sosialidemokraattinen eduskuntaryhmä"),
        ("tests/data/xmls/kilpi.xml", "Parliamentary Group of the National Coalition Party"),
        ("tests/data/xmls/rehn-kivi.xml", "Swedish Parliamentary Group"),
        ("tests/data/xmls/suomela.xml", "Green Parliamentary Group"),
    ],
    indirect=["mpinfo"],
)
def test_get_party(mpinfo: MPInfo, true_party: str) -> None:
    """Test that party (/parliamentary group) is correctly parsed from the XML."""
    party = mpinfo.get_party()
    assert party == true_party


@pytest.mark.parametrize(
    "mpinfo, true_profession",
    [
        ("tests/data/xmls/ahde.xml", ""),
        ("tests/data/xmls/kilpi.xml", "police officer, writer"),
        ("tests/data/xmls/rehn-kivi.xml", "architect, building supervision manager"),
        ("tests/data/xmls/suomela.xml", "student of social sciences"),
    ],
    indirect=["mpinfo"],
)
def test_get_profession(mpinfo: MPInfo, true_profession: str) -> None:
    """Test that profession is correctly parsed from the XML."""
    profession = mpinfo.get_profession()
    assert profession == true_profession


@pytest.mark.parametrize(
    "mpinfo, true_city",
    [
        ("tests/data/xmls/ahde.xml", ""),
        ("tests/data/xmls/kilpi.xml", "Kuopio"),
        ("tests/data/xmls/rehn-kivi.xml", "Kauniainen"),
        ("tests/data/xmls/suomela.xml", "Tampere"),
    ],
    indirect=["mpinfo"],
)
def test_get_city(mpinfo: MPInfo, true_city: str) -> None:
    """Test that current home city is correctly parsed from the XML."""
    city = mpinfo.get_city()
    assert city == true_city


@pytest.mark.parametrize(
    "mpinfo, true_pob",
    [
        ("tests/data/xmls/ahde.xml", "Oulu"),
        ("tests/data/xmls/kilpi.xml", "Rovaniemi"),
        ("tests/data/xmls/rehn-kivi.xml", "Helsinki"),
        ("tests/data/xmls/suomela.xml", ""),
    ],
    indirect=["mpinfo"],
)
def test_get_pob(mpinfo: MPInfo, true_pob: str) -> None:
    """Test that place of birth is correctly parsed from the XML."""
    pob = mpinfo.get_pob()
    assert pob == true_pob


@pytest.mark.parametrize(
    "mpinfo, true_districts",
    [
        (
            "tests/data/xmls/ahde.xml",
            "Oulun läänin vaalipiiri (03/1970-06/1990), Oulun vaalipiiri (03/2003-04/2011)",
        ),
        ("tests/data/xmls/kilpi.xml", "Electoral District of Savo-Karelia (04/2019-)"),
        ("tests/data/xmls/rehn-kivi.xml", "Electoral District of Uusimaa (08/2016-)"),
        ("tests/data/xmls/suomela.xml", "Electoral District of Pirkanmaa (04/2019-)"),
    ],
    indirect=["mpinfo"],
)
def test_get_districts(mpinfo: MPInfo, true_districts: str) -> None:
    """Test that electoral districts are correctly parsed from the XML."""
    districts = mpinfo.get_districts()
    assert districts == true_districts


@pytest.mark.parametrize(
    "mpinfo, true_education",
    [
        ("tests/data/xmls/ahde.xml", "kansakoulu, ammattikoulu, kansankorkeakoulu"),
        ("tests/data/xmls/kilpi.xml", "Degree in policing"),
        ("tests/data/xmls/rehn-kivi.xml", "architect"),
        ("tests/data/xmls/suomela.xml", ""),
    ],
    indirect=["mpinfo"],
)
def test_get_education(mpinfo: MPInfo, true_education: str) -> None:
    """Test that degree names and education are correctly parsed from the XML."""
    education = mpinfo.get_education()
    assert education == true_education


@pytest.mark.parametrize(
    "mpinfo, mpid, firstname, lastname, true_mp",
    [
        ("tests/data/xmls/ahde.xml", 103, "Matti", "Ahde", 0),
        ("tests/data/xmls/kilpi.xml", 1432, "Marko", "Kilpi", 1),
        ("tests/data/xmls/rehn-kivi.xml", 1374, "Veronica", "Rehn-Kivi", 2),
        ("tests/data/xmls/suomela.xml", 1423, "Iiris", "Suomela", 3),
    ],
    indirect=["mpinfo", "true_mp"],
)
def test_mpinfo_parse(
    mpinfo: MPInfo, mpid: int, firstname: str, lastname: str, true_mp: MP
) -> None:
    """Test that MP info is correctly parsed from the XML to an MP object."""
    mp = mpinfo.parse(mpid, firstname, lastname)
    assert mp == true_mp
