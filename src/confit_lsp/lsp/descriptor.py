from dataclasses import dataclass
from functools import cached_property
from typing import Any, Self, Sequence
from lsprotocol.types import Position
import rtoml


from .parsers import parse_toml
from .parsers import Element, ElementPath


@dataclass
class ConfigurationView:
    data: dict[str, Any]
    """The actual data."""

    elements: list[Element]
    """Key-value ranges for look-up."""

    @cached_property
    def path2element(self) -> dict[ElementPath, Element]:
        return {element.path: element for element in self.elements}

    def get_element_from_position(self, position: Position) -> Element | None:
        for element in self.elements:
            if element.key.start <= position < element.value.end:
                return element
        return None

    def get_value(self, path: Sequence[str]) -> Any:
        return self.get_object(path[:-1])[path[-1]]

    def get_object(
        self,
        path: Sequence[str],
    ) -> dict[str, Any]:
        """Get the underlying object at a given path by recursively querying keys."""

        d = self.data

        for key in path:
            d = d[key]

        return d

    @classmethod
    def from_source(cls, content: str) -> Self:
        data = rtoml.loads(content)
        elements = list(parse_toml(content))

        return cls(
            data=data,
            elements=elements,
        )
