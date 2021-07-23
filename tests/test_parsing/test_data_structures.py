"""Test methods in data structures."""
from unittest import mock
from unittest.mock import MagicMock

from fi_parliament_tools.parsing.data_structures import Transcript


@mock.patch("fi_parliament_tools.parsing.data_structures.json.dump")
@mock.patch("fi_parliament_tools.parsing.data_structures.atomic_write")
def test_save_to_json(mocked_atomic_write: MagicMock, mocked_dump: MagicMock) -> None:
    """Test saving of transcript to a JSON file."""
    transcript = Transcript(0, 0, "YYYY-MM-DDTHH:MM:SS")
    transcript.save_to_json("some_path")
    mocked_atomic_write.assert_called_once_with("some_path", mode="w", encoding="utf-8")
    mocked_dump.assert_called_once_with(
        {"number": 0, "year": 0, "begin_time": "YYYY-MM-DDTHH:MM:SS", "subsections": []},
        mocked_atomic_write().__enter__(),
        ensure_ascii=False,
        indent=2,
    )
