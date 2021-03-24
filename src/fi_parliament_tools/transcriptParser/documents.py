#!/usr/bin/env python3
# coding=utf-8
"""Parsers for handling different parliament documents published after 2015."""
import json
import pathlib
import re
from dataclasses import asdict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import py
from lxml import etree

from fi_parliament_tools.transcriptParser.data_structures import EmbeddedStatement
from fi_parliament_tools.transcriptParser.data_structures import Statement
from fi_parliament_tools.transcriptParser.data_structures import Subsection
from fi_parliament_tools.transcriptParser.data_structures import Transcript
from fi_parliament_tools.transcriptParser.query import SessionQuery
from fi_parliament_tools.transcriptParser.query import StatementQuery
from fi_parliament_tools.transcriptParser.query import VaskiQuery


class Session:
    """A class for handling XML formatted parliament session transcripts."""

    def __init__(self, number: int, year: int, xml_root: etree):
        """Initialize Session object from the given session number, year and xml.

        Args:
            number (int): running number for the session
            year (int): working year of the session
            xml_root (etree): root of the XML document containing the transcript
        """
        self.number = number
        self.year = year
        self.id = f"PTK {self.number}/{self.year} vp"
        self.query_key = f"{self.year}/{self.number}"
        self.statement_fields = [
            "Type",
            "MP ID",
            "Firstname",
            "Lastname",
            "Affiliation",
            "Title",
            "Start time",
            "End time",
            "Language",
            "Statement",
            "Embedded title",
            "Embedded firstname",
            "Embedded lastname",
            "Embedded statement",
        ]

        [self.xml_transcript] = xml_root.xpath(
            "//*[local-name() = 'Siirto']//*[local-name() = 'Poytakirja']"
        )

    def get_chairman_info(self, xml_element: etree._Element) -> Tuple[str, str, str]:
        """Get the chairman title and name from an XML element.

        In the transcript xmls the chairman info is in one string. General format is:
        (First/Second) (Vice)Chairman Firstname Lastname

        Args:
            xml_element (etree._Element): a chairman statement ('PuheenjohtajaRepliikki')

        Returns:
            str: chairman title
            str: firstname
            str: lastname
        """
        [info] = xml_element.xpath('. //*[local-name() = "PuheenjohtajaTeksti"]/text()')
        info = info.split(" ")
        if len(info) < 3:
            return (" ".join(info), "", "")
        return (" ".join(info[:-2]), info[-2], info[-1])

    def get_short_statement_text(self, xml_element: etree._Element) -> str:
        """Get the text transcript of a short/chairman statement.

        Short statements have the name 'PuhujaRepliikki' and chairman statements have the name
        'PuheenjohtajaRepliikki.

        Args:
            xml_element (etree._Element): a short statement ('Puhuja/PuheenjohtajaRepliikki')

        Returns:
            str: statement text
        """
        text = xml_element.xpath('. //*[local-name() = "KappaleKooste"]//text()')
        return " ".join([paragraph.strip() for paragraph in text])

    def get_speaker_info(self, xml_element: etree._Element) -> Tuple[int, str, str, str, str]:
        """Get information about the speaker from the xml_element.

        The info includes MP id, name and party/title. MP id is unique identifier given to
        all MPs past and present in the parliament databases. The id can be used to fetch other
        information about the MPs from parliament databases, like speaker gender.

        For party and title, only one is usually defined. The missing one is returned as an
        empty string. Cabinet ministers have a minister title but no party. The opposite applies to
        regular members of the parliament (party but no title). The party field may have extra
        strings sometimes, which is why we take only the first element.

        In some very rare cases, the speaker is not a member of parliament but for example the
        attorney general. In these cases, the MP id is set to 0 and the title is processed
        again.

        Args:
            xml_element (etree._Element): speaker part of a speaker statement ('Toimija')

        Returns:
            int: MP id
            str: firstname
            str: lastname
            str: party
            str: title
        """
        firstname = "".join(xml_element.xpath('. //*[local-name() = "EtuNimi"]/text()')).strip()
        lastname = "".join(xml_element.xpath('. //*[local-name() = "SukuNimi"]/text()')).strip()
        party = "".join(xml_element.xpath('(. //*[local-name() = "LisatietoTeksti"])[1]/text()'))
        title = "".join(xml_element.xpath('. //*[local-name() = "AsemaTeksti"]/text()')).strip()
        if not (mp_id := xml_element.xpath("string(. //@*[local-name() = 'muuTunnus'])").strip()):
            mp_id = "0"
            title = "".join(xml_element.xpath('. /@*[local-name() = "rooliKoodi"]')).strip()
        return (int(mp_id), firstname, lastname, party, re.sub(" +", " ", title))

    def get_speaker_statement_text(self, xml_element: etree._Element) -> List[str]:
        """Get the statement of the speaker from the xml_element.

        Args:
            xml_element (etree._Element): speech part of a speaker statement ('PuheenvuoroOsa')

        Returns:
            list: the statement split into a list of paragraph strings
        """
        text = xml_element.xpath(
            '. /*[local-name() = "KohtaSisalto"]/*[local-name() = "KappaleKooste"]/text()'
        )
        return [paragraph.strip() for paragraph in text]

    def get_speaker_statement_timestamps(self, xml_element: etree._Element) -> Tuple[str, str]:
        """Get the start and end timestamps of a speaker statement from the xml_element.

        Args:
            xml_element (etree._Element): speech part of a speaker statement ('PuheenvuoroOsa')

        Returns:
            str: statement start time as "YYYY-MM-DDTHH:MM:SS" or empty str if missing
            str: statement end time as "YYYY-MM-DDTHH:MM:SS" or empty str if missing
        """
        if not (start_time := xml_element.xpath(". /@*[local-name() = 'puheenvuoroAloitusHetki']")):
            start_time = [""]
        if not (end_time := xml_element.xpath(". /@*[local-name() = 'puheenvuoroLopetusHetki']")):
            end_time = [""]
        return (start_time[0], end_time[0])

    def get_language_code(self, xml_element: etree._Element) -> str:
        """Get the language code of a speaker statement from the xml_element.

        The 'kieliKoodi' attribute is always Finnish and statements are assumed to be Finnish by
        default. However, if the MP speaks in Swedish, the xml_element will have a second attribute
        called 'toinenKieliKoodi'.

        Args:
            xml_element (etree._Element): speech part of a speaker statement ('PuheenvuoroOsa')

        Returns:
            str: the language code as a string ('fi' or 'sv')
        """
        has_second_language: str = xml_element.xpath(
            "string(. /@*[local-name() = 'toinenKieliKoodi'])"
        )
        if has_second_language:
            return has_second_language
        language: str = xml_element.xpath("string(. /@*[local-name() = 'kieliKoodi'])")
        return language

    def compose_chairman_statement(self, xml_element: etree._Element) -> Statement:
        """Compose a chairman statement object from the given xml_element.

        Args:
            xml_element (etree._Element): a chairman statement ('PuheenjohtajaRepliikki')

        Returns:
            Statement: all the statement data
        """
        title, firstname, lastname = self.get_chairman_info(xml_element)
        text = self.get_short_statement_text(xml_element)
        embedded = EmbeddedStatement("", "", "", "")
        return Statement("C", 0, firstname, lastname, "", title, "", "", "", text, embedded)

    def compose_short_statement(self, xml_element: etree._Element) -> Statement:
        """Compose a short speaker statement object from the given XML element.

        Args:
            xml_element (etree._Element): a short speaker turn ('PuhujaRepliikki')

        Returns:
            Statement: a data object that contains all speaker statement data
        """
        [speaker_element] = xml_element.xpath(". /*[local-name() = 'Toimija']")
        mp_id, firstname, lastname, party, title = self.get_speaker_info(speaker_element)
        text = self.get_short_statement_text(xml_element)
        embedded = EmbeddedStatement("", "", "", "")
        return Statement("S", mp_id, firstname, lastname, party, title, "", "", "", text, embedded)

    def compose_speaker_statements(self, xml_element: etree._Element) -> List[Statement]:
        """Compose long statements from the given xml_element.

        Most long statements have only one speech element. However, some MPs switch between Finnish
        and Swedish in their speech. Different languages are separated to their own speech elements.

        Args:
            xml_element (etree._Element): a speaker turn ('PuheenvuoroToimenpide')

        Returns:
            Statement: a data object that contains all speaker statement data
        """
        [speaker_element] = xml_element.xpath(". /*[local-name() = 'Toimija']")
        speech_elements = xml_element.xpath(". /*[local-name() = 'PuheenvuoroOsa']")
        mp_id, fname, lname, party, title = self.get_speaker_info(speaker_element)
        statements = []
        for speech in speech_elements:
            start, end = self.get_speaker_statement_timestamps(speech)
            lang = self.get_language_code(speech)
            texts = self.get_speaker_statement_text(speech)
            embed = self.check_embedded_statement(speech, texts)
            text = " ".join(texts)
            statements.append(
                Statement("L", mp_id, fname, lname, party, title, start, end, lang, text, embed)
            )
        return statements

    def check_embedded_statement(
        self, xml_element: etree._Element, main_text: List[str]
    ) -> EmbeddedStatement:
        """Check whether a speaker statement contains an embedded statement.

        If the statement has embedded speech from the chairman, the place of the embedded speech
        within the speaker text is marked with `#ch_statement` for later processing.

        Args:
            xml_element (etree._Element): speech part of a speaker statement ('PuheenvuoroOsa')
            main_text (list): text paragraphs of the main statement

        Returns:
            EmbeddedStatement: an object that contains all the embedded statement data
        """
        for i, element in enumerate(xml_element.xpath(". /*[local-name() = 'KohtaSisalto']/*")):
            if "PuheenjohtajaRepliikki" in element.tag:
                title, firstname, lastname = self.get_chairman_info(element)
                text = self.get_short_statement_text(element)
                main_text.insert(i, "#ch_statement")
                return EmbeddedStatement(title, firstname, lastname, text)
        return EmbeddedStatement("", "", "", "")

    def get_session_start_time(self) -> str:
        """Get the true session start time from a database.

        The database stores timestamps in the format 'YYYY-MM-DD HH:MM:SS.sss'.

        Returns:
            str: The session date and start time
        """
        start_time = SessionQuery(self.query_key).get_session_start_time()
        if not start_time:
            [start_time] = self.xml_transcript.xpath(". /@*[local-name() = 'kokousAloitusHetki']")
        return start_time

    def parse_to_json(self, path: Union[str, pathlib.Path, py.path.local]) -> None:
        """Parse the session transcript into a JSON file defined in the path.

        Args:
            path (str): path to the JSON file
        """
        start_time = self.get_session_start_time()
        transcript = Transcript(self.number, self.year, start_time)
        subsections = self.xml_transcript.xpath(
            ". /*[local-name() = 'MuuAsiakohta' or local-name() = 'Asiakohta']"
        )
        for subsec in subsections:
            if (processed := self.process_subsection(subsec)) is not None:
                transcript.subsections.append(processed)
        with open(path, "w", encoding="utf-8") as outfile:
            json.dump(asdict(transcript), outfile, ensure_ascii=False, indent=2)
            outfile.write("\n")

    def process_subsection(self, xml_element: etree._Element) -> Optional[Subsection]:
        """Process the statements in a session subsection and save them into a JSON file.

        Args:
            xml_element (etree._Element): a session subsection ('MuuAsiakohta/Asiakohta')

        Returns:
            Subsection: a subsection if there are any speech transcripts in it
        """
        statement_elements = xml_element.xpath(
            ". /*[local-name() = 'Toimenpide']//*[local-name() = 'PuheenjohtajaRepliikki' or "
            "local-name() = 'PuhujaRepliikki'] | . //*[local-name() = 'PuheenvuoroToimenpide']"
        )
        if not statement_elements:
            return None
        [subsection_number] = xml_element.xpath(". /*[local-name() = 'KohtaNumero']/text()")
        subsection = Subsection(subsection_number)
        for element in statement_elements:
            if "PuheenvuoroToimenpide" in element.tag:
                subsection.statements.extend(self.compose_speaker_statements(element))
            elif "PuhujaRepliikki" in element.tag:
                subsection.statements.append(self.compose_short_statement(element))
            else:
                subsection.statements.append(self.compose_chairman_statement(element))
        if self.contains_interpellation(xml_element):
            subsection.statements.append(self.process_interpellation(xml_element))
        return subsection

    def contains_interpellation(self, xml_element: etree._Element) -> bool:
        """Check if the session subsection contains an interpellation.

        Args:
            xml_element (etree._Element): a session subsection ('MuuAsiakohta/Asiakohta')

        Returns:
            bool: True if the subsection contains an interpellation
        """
        has_interpellation: bool = xml_element.xpath(
            "boolean(. //*[local-name() = 'AsiakirjatyyppiNimi']/text() = 'Välikysymys')"
        )
        return has_interpellation

    def process_interpellation(self, xml_element: etree._Element) -> Statement:
        """Fetch and process the interpellation statement within the subsection.

        Args:
            xml_element (etree._Element): a session subsection ('MuuAsiakohta/Asiakohta')

        Returns:
            Statement: a data object that contains all interpellation statement data
        """
        [interp_id] = xml_element.xpath(". //*[local-name() = 'EduskuntaTunnus']/text()")
        interp_number, interp_year = re.findall(r"\d+", interp_id)
        xml = etree.fromstring(VaskiQuery(interp_id, doc_type="Interpellation").get_xml())
        interpellation = Interpellation(interp_number, interp_year, xml, self.query_key)
        return interpellation.compose_speaker_statement()


class Interpellation(Session):
    """Interpellations (välikysymys) are a variation of the general parliament session transcript.

    Interpellations are published separate from the main transcript but have a similar XML
    structure.
    """

    def __init__(self, number: int, year: int, xml_root: etree, session: str):
        """Initialize Interpellation object from the given session number, year and xml.

        Args:
            number (int): interpellation number as an integer
            year (int): year of the session
            xml_root (etree): root of the XML document containing the interpellation
            session (str): the parliament session that contains the interpellation ('year/number')
        """
        self.number = number
        self.year = year
        self.session = session

        [self.xml_transcript] = xml_root.xpath(
            "/*[local-name() = 'Siirto']//*[local-name() = 'Kysymys']"
        )

    def get_interpellation_text(self) -> str:
        """Get the interpellation text from the interpellation xml document.

        The last paragraph (PonsiOsa) of the interpellation consists of a list of questions
        that are here joined to form a single paragraph.

        Returns:
            str: The interpellation text as a very long string
        """
        text = self.xml_transcript.xpath(". //*[local-name() = 'KappaleKooste']/text()")
        questions = self.xml_transcript.xpath(
            ". //*[local-name() = 'JohdantoTeksti']/text() |"
            " //*[local-name() = 'SisennettyKappaleKooste']"
            "/*[local-name() = 'KursiiviTeksti']/text()"
        )
        text += questions
        return " ".join([paragraph.strip() for paragraph in text])

    def query_timestamp(self, mp_id: str) -> str:
        """Query interpellation statement start time from speaker turn database.

        Statement end timestamps are not available in the database. The database stores timestamps
        in the format 'YYYY-MM-DD HH:MM:SS.sss'.

        Args:
            mp_id (str): unique MP id of the speaker

        Returns:
            str: the start timestamp of a speaker turn
        """
        query = StatementQuery(self.session)
        start_time = query.search_interpellation_speaker_turn(mp_id)
        return start_time

    def compose_speaker_statement(self) -> Statement:
        """Compose interpellation as a speaker statement.

        For interpellations it is assumed that language is always Finnish and that there are no
        embedded chairman statements.

        Returns:
            Statement: a data object that contains all statement data
        """
        [speaker_element] = self.xml_transcript.xpath(
            ". /*[local-name() = 'IdentifiointiOsa']/*[local-name() = 'Toimija']"
        )
        mp_id, firstname, lastname, party, title = self.get_speaker_info(speaker_element)
        text = self.get_interpellation_text()
        start = self.query_timestamp(str(mp_id))
        embedded = EmbeddedStatement("", "", "", "")
        return Statement(
            "L", mp_id, firstname, lastname, party, title, start, "", "fi", text, embedded
        )
