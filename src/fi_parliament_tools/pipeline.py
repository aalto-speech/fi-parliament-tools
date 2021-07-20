"""Pipeline class implements functionality that is common to all processing pipelines."""
from logging import Logger
from typing import List


class Pipeline:
    """Pipeline template for different workflows."""

    def __init__(self, log: Logger) -> None:
        """Initialize parameters common to all pipelines.

        Args:
            log (Logger): logger object
        """
        self.log = log
        self.errors: List[str] = []
