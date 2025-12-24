from dataclasses import dataclass
from functools import cached_property
import logging
from typing import Any, Literal, Self, Sequence, assert_never
from lsprotocol.types import Position, Range
import rtoml

from collections import deque


from .parsers import parse_toml
from .parsers import ElementPath

logger = logging.getLogger(__name__)


@dataclass
class ConfigurationView:
    data: dict[str, Any]
    """The actual data."""

    keys: dict[ElementPath, Range]
    """Key path to range lookup table."""

    values: dict[ElementPath, Range]
    """Value path to range lookup table."""

    @cached_property
    def path_range(self) -> list[tuple[ElementPath, Range]]:
        result = list[tuple[ElementPath, Range]]()

        for path, location in self.keys.items():
            if (value := self.values.get(path)) is not None:
                location = Range(start=location.start, end=value.end)
                location.end = value.end
            result.append((path, location))

        return result

    @cached_property
    def references(self) -> dict[ElementPath, ElementPath]:
        """In-document references."""
        path2path = dict[ElementPath, ElementPath]()

        to_visit = deque[tuple[ElementPath, dict[str, Any]]]()
        to_visit.append(((), self.data))

        while len(to_visit) > 0:
            path, data = to_visit.popleft()

            for key, value in data.items():
                new_path = (*path, key)
                if isinstance(value, dict):
                    to_visit.append((new_path, value))

                if not isinstance(value, str):
                    continue

                if not value.startswith("$"):
                    continue

                path2path[new_path] = tuple(value[1:].split("."))

        return path2path

    def get_element_from_position(
        self,
        position: Position,
    ) -> tuple[Literal["key", "value", "line"], ElementPath] | None:
        for path, location in self.path_range:
            if location.start <= position < location.end:
                break
        else:
            return None

        key = self.keys[path]

        if key.start <= position < key.end:
            return "key", path

        value = self.values.get(path)
        if value is None:
            return "line", path

        if value.start <= position < value.end:
            return "value", path

        return "line", path

    def get_value(
        self,
        path: Sequence[str],
    ) -> Any:
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

    def factories(self) -> list[ElementPath]:
        result = list[ElementPath]()
        for path in self.keys.keys():
            *path, key = path
            if key == "factory":
                result.append(tuple(path))
        return result

    @classmethod
    def from_source(
        cls,
        content: str,
    ) -> Self:
        data = rtoml.loads(content)

        keys = dict[ElementPath, Range]()
        values = dict[ElementPath, Range]()

        for kind, element in parse_toml(content):
            if kind == "key":
                keys[element.path] = element.location
            elif kind == "value":
                values[element.path] = element.location
            else:
                assert_never(kind)

        return cls(
            data=data,
            keys=keys,
            values=values,
        )
