"""Pipeline class implements functionality that is common to all processing pipelines."""
from logging import Logger
from pathlib import Path
from typing import List


class Pipeline:
    """Pipeline template for different workflows."""

    def __init__(self, input_files: List[str], log: Logger) -> None:
        """Initialize parameters common to all pipelines.

        Args:
            input_files (List[str]): list of files to process in the pipeline
            log (Logger): logger object
        """
        self.input_files = [Path(input_file).resolve() for input_file in input_files]
        self.log = log
        self.errors: List[str] = []
