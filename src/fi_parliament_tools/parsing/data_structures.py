"""Several dataclasses for storing all transcript related data.

Statements are split into two varietes, embedded and speaker statements. Embedded statement appears
as part of a speaker statement. Embedded statements contain only minimal amount of information
while speaker statements can have more associated data.

Statements are grouped into subsections, which form a session transcript. Session transcripts are
identified by a running number and parliament working year. The session start time is also saved
for later processing.

Slots are used to optimize memory consumption and processing speed.
"""
import json
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Union

from atomicwrites import atomic_write


@dataclass
class EmbeddedStatement:
    """Embedded statements are chairman comments contained within long speaker statements.

    Timestamps and party are never defined for embedded statements, so they are left out.
    """

    __slots__ = [
        "mp_id",
        "title",
        "firstname",
        "lastname",
        "language",
        "text",
        "offset",
        "duration",
    ]
    mp_id: int
    title: str
    firstname: str
    lastname: str
    language: str
    text: str
    offset: float
    duration: float


@dataclass
class Statement:
    """A statement contains speaker+statement statistics and a possible embedded short statement.

    Speaker statistics related to the statement include the first and last names of the speaker,
    their party/title and a unique mp id.
    Statement related data contains rough start and end timestamps (in datetime format), language,
    and the statement transcript text.
    Offset and duration mark the beginning of the statement and its duration in seconds in the
    audio file. These are determined in the postprocessing of alignment results, they do not exist
    in the XML transcripts.
    Some speaker statements also contain embedded chairman statements within them, spoken somewhere
    in the middle of the speaker statement. These need to be included for later processing stages.

    Statements are split to three types L(ong), S(hort) and C(hairman) statements:
     1. Long statements are spoken by MPs. In long statements timestamps and language are defined.
        They might also contain embedded statements.
     2. Short statements are spoken by MPs, but they are missing timestamps and language. They also
        will not contain embedded statements. These appear in sessions with voting.
     3. Chairman statements have only firstname, lastname, title and text defined.

    """

    __slots__ = [
        "type",
        "mp_id",
        "firstname",
        "lastname",
        "party",
        "title",
        "start_time",
        "end_time",
        "language",
        "text",
        "offset",
        "duration",
        "embedded_statement",
    ]
    type: str
    mp_id: int
    firstname: str
    lastname: str
    party: str
    title: str
    start_time: str
    end_time: str
    language: str
    text: str
    offset: float
    duration: float
    embedded_statement: EmbeddedStatement


@dataclass
class Subsection:
    """A session transcript is split into subsections.

    Each subsection has a number and a topic title according to the transcript table of contents
    and the associated statements. Only subsections with statements are saved in parsing, rest are
    ignored.

    Note that on rare occasions subsections do not follow strictly chronological order. In these
    cases, discussion on a subsection topic begins and continues so long that chairman decides to
    interrupt it. Then following subsections are discussed first before returning to the subsection
    with the long discussion. In other words, statements are chronologically ordered within a
    subsection but not always on the transcript level.
    """

    number: str
    title: str
    statements: List[Statement] = field(default_factory=list)


@dataclass
class Transcript:
    """A session transcript is the main data structure for saving parsed transcripts.

    Each session is associated with a running number and parliamentary working year. The working
    year differs from calendar year on election years. Session start time is recorded but its
    accuracy may vary because sometimes only the planned start time is available. Each transcript
    is further split into subsections.
    """

    number: int
    year: int
    begin_time: str
    subsections: List[Subsection] = field(default_factory=list)

    def save_to_json(self, path: Union[str, Path]) -> None:
        """Save the transcript to a JSON file.

        Args:
            path (Union[str, Path]): path to the JSON file
        """
        with atomic_write(path, mode="w", encoding="utf-8") as outfile:
            json.dump(asdict(self), outfile, ensure_ascii=False, indent=2)
            outfile.write("\n")


@dataclass
class MP:
    """A member of parliament data structure for saving basic information about an MP.

    Gender is either 'm' for male or 'f' for female. Language refers to mother tongue, either
    Finnish or Swedish. Party field contains the party the MP represents at the time this object
    is created. Profession field may contain multiple different professions and/or the highest
    educational degree the MP holds.

    City field contains the municipality the MP currently resides in. Place of birth (pob) defines
    the municipality/city the MP was born in. Pob-field may contain a foreign city or a
    (Finnish) municipality that has ceased to exist.
    """

    __slots__ = [
        "mp_id",
        "firstname",
        "lastname",
        "gender",
        "lang",
        "birthyear",
        "party",
        "profession",
        "city",
        "pob",
    ]
    mp_id: int
    firstname: str
    lastname: str
    gender: str
    lang: str
    birthyear: int
    party: str
    profession: str
    city: str
    pob: str


def decode_transcript(
    dct: Dict[Any, Any],
) -> Union[EmbeddedStatement, Statement, Subsection, Transcript, Dict[Any, Any]]:
    """Deserialize transcript json back into a custom document object.

    Args:
        dct (dict): a (nested) dict in the JSON file to deserialize

    Returns:
        documents.Object: the dictionary as a correct custom object
    """
    if "title" in dct.keys() and len(dct) == 8:
        return EmbeddedStatement(**dct)
    if "title" in dct.keys() and len(dct) > 8:
        return Statement(**dct)
    if "statements" in dct.keys():
        return Subsection(**dct)
    if "subsections" in dct.keys():
        return Transcript(**dct)
    return dct  # pragma: no cover
