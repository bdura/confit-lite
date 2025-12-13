from dataclasses import dataclass
from typing import Iterator, Protocol
from lsprotocol.types import Range


ElementPath = tuple[str, ...]


@dataclass
class Element:
    """A configuration element, with key/value location - for LSP purposes.

    Defined by the path within the underlying dictionary, and the key and value ranges.
    """

    path: ElementPath

    key: Range
    value: Range


class ConfigurationParser(Protocol):
    """The protocol configuration parsers should adhere to."""

    def __call__(self, content: str) -> Iterator[Element]: ...
