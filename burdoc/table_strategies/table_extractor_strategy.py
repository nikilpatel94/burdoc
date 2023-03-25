import abc
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from ..utils.logging import get_logger


class TableExtractorStrategy(abc.ABC):
    """Abstract base class defining the interface for table extraction methods. This is consistent between ML and rules based methods"""

    class TableParts(Enum):
        """Enum defining the different parts of a table that can be extracted"""
        TABLE = 0
        COLUMN = 1
        ROW = 2
        COLUMNHEADER = 3
        ROWHEADER = 4
        SPANNINGCELL = 5

    def __init__(self, name: str, log_level: int=logging.INFO):
        self.name = name
        self.log_level = log_level
        self.logger = get_logger(name, log_level=log_level)


    @abc.abstractmethod
    @staticmethod
    def requirements() -> List[str]:
        '''Return list of data requirements for this strategy'''

    @abc.abstractmethod
    def extract_tables(self, **kwargs) -> List[Dict[int, Any]]:
        '''Extracts tables and returns them in a complex JSON format'''