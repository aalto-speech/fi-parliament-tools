"""Several dataclasses for storing all transcript related data.

Statements are split into two varietes, embedded and speaker statements. Embedded statement appears
as part of a speaker statement. Embedded statements contain only minimal amount of information
while speaker statements can have more associated data.

Statements are grouped into subsections, which form a session transcript. Session transcripts are
identified by a running number and parliament working year. The session start time is also saved
for later processing.

Slots are used to optimize memory consumption and processing speed.
"""
from dataclasses import dataclass
from dataclasses import field
from typing import List


@dataclass(frozen=True)
class EmbeddedStatement:
    """An embedded statement consists of only the speaker name, title and the statement itself.

    Embedded statements are chairman comments contained within long speaker statements.
    """

    __slots__ = ["title", "firstname", "lastname", "text"]
    title: str
    firstname: str
    lastname: str
    text: str


@dataclass(frozen=True)
class Statement:
    """A statement contains speaker+statement statistics and a possible embedded short statement.

    Speaker statistics related to the statement include the first and last names of the speaker,
    their party/title and a unique mp id.
    Statement related data contains start and end timestamps, language and the statement
    transcript.
    Some speaker statements also contain embedded chairman statements within them, spoken somewhere
    in the middle of the speaker statement. These need to be included for later processing stages.

    Statements are split to three types L(ong), S(hort) and C(hairman) statements:
     1. Long statements are spoken by MPs. In long statements timestamps and language are defined.
        They might also contain embedded statements.
     2. Short statements are spoken by MPs, but they are missing timestamps and language. They also
        will not contain embedded statements. These appear in sessions with voting.
     3. Chairman statements have always only firstname, lastname, title and text defined.

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
    embedded_statement: EmbeddedStatement


@dataclass
class Subsection:
    """A session transcript is split into subsections.

    Each subsection has a number according to the transcript table of contents and the associated
    statements. Only subsections with statements are saved in parsing, rest are ignored.
    """

    number: str
    statements: List[Statement] = field(default_factory=list)


@dataclass
class Transcript:
    """A session transcript is the main data structure for saving parsed transcripts.

    Each session is associated with a running number and parliamentary working year. Session start
    time is also recorded. Each transcript is further split into subsections.
    """

    number: int
    year: int
    begin_time: str
    subsections: List[Subsection] = field(default_factory=list)
