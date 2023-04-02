import abc
import logging
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

from plotly.graph_objects import Figure

from ..utils.logging import get_logger


class Processor(abc.ABC):
    """Abstract base class for a general Processor.
    Processors receive data in a single blob, extract any needed data, then write new
    or updated fields back to the data store.
    """

    name: str = "processor"
    threadable = True
    expensive = False

    def __init__(self, name: str, log_level: int = logging.INFO, max_threads: Optional[int] = None):
        self.name = name
        self.logger = get_logger(name, log_level=log_level)
        self.max_threads = max_threads

    def initialise(self):
        '''Perform any expensive operations required to create a processor'''

    @abc.abstractmethod
    def requirements(self) -> Tuple[List[str], List[str]]:
        '''Return list of required data fields and list of optional data fields'''

    @abc.abstractmethod
    def generates(self) -> List[str]:
        '''Return list of fields added by this processor'''

    @abc.abstractmethod
    def _process(self, data: Any) -> Any:
        '''Transforms the processed data'''

    def process(self, data: Any) -> Any:
        '''Transforms the processed data'''
        if self.name not in data['performance']:
            data['performance'][self.name] = {}
        start = time.perf_counter()
        self._process(data)
        duration = time.perf_counter() - start
        data['performance'][self.name]['process'] = [round(duration, 3)]

    def get_page_data(self, data: Dict[str, Dict[int, Any]], page_number: Optional[int] = None) -> Iterator[List[Any]]:
        """Returns an iterable of the passed data segmented by page number. Optional requirements
        are returned as 'None' if not present

        Args:
            data (Dict[str, Dict[int, Any]]): Primary data store
            page_number (Optional[int], optional): Return a specific page's data. Defaults to None.

        Yields:
            Iterator[List[Any]]: An iterator over the page-grouped fields
        """
        reqs = self.requirements()
        if page_number:
            pages = [page_number]
        else:
            pages = list(data[reqs[0][0]].keys())
        for number in pages:
            yield [number] + [data[r][number] for r in reqs[0]] + [data[r][number] if r in data else None for r in reqs[1]]

    def get_data(self, data: Any) -> List[Dict[int, Any]]:
        """Returns all of the data in a list of required fields. Optional requirements
        are returned as 'None' if not present

        Args:
            data (Any): Primary data store

        Returns:
            List[Dict[int, Any]]: List of fields
        """
        reqs = self.requirements()
        return [data[r] for r in reqs[0]] + [data[r] if r in data else None for r in reqs[1]]

    def check_requirements(self, data: Any) -> bool:
        """Checks that required data fields are present in the data.

        Args:
            data (Any): Primary data store

        Returns:
            bool: Are all fields present
        """

        for r in self.requirements()[0]:
            if r not in data:
                self.logger.error("Missing required data field %s", r)
                return False
        return True

    @abc.abstractmethod
    def add_generated_items_to_fig(self, page_number: int, fig: Figure, data: Dict[str, Any]):
        '''Draw any items generated by this processor to a page image'''
