from dataclasses import dataclass
from functools import cached_property
from itertools import chain
from pathlib import Path
from typing import Any, NewType, Self, assert_never
from persil.result import Err
import rtoml

from persil import string, regex, whitespace

key = regex(r"[a-zA-z_-]\w*")
path = key.sep_by(string("."), min=1)

left_bracket = string("[")
right_bracket = string("]")

table = left_bracket >> path << right_bracket

line_remainder = regex(".*")

newline = string("\n")
comment = string("#") >> line_remainder

discarded = newline | comment

parser = whitespace.optional() >> (
    table.map(lambda path: ("title", path)).desc("table title")
    | (path.map(lambda path: ("element", path)) << line_remainder).desc("key")
    | discarded.result(("discarded", None)).desc("discarded")
)


LineNumber = NewType("LineNumber", int)
FullKey = tuple[str, str]

TomlDict = dict[str, Any]


@dataclass
class Data:
    data: TomlDict
    path2line: dict[FullKey, LineNumber]

    def get_root(self, path: str) -> TomlDict:
        d = self.data

        for key in path.split("."):
            d = d[key]

        return d

    @cached_property
    def line2path(self) -> dict[LineNumber, FullKey]:
        return {line_number: path for path, line_number in self.path2line.items()}

    @classmethod
    def from_file(cls, filepath: Path) -> Self:
        content = filepath.read_text()
        return cls.from_source(content)

    @classmethod
    def from_source(cls, content: str) -> Self:
        data = rtoml.loads(content)

        path2line = dict[FullKey, LineNumber]()

        current_table = list[str]()
        line_number = 0

        while True:
            try:
                result, content = parser.parse_partial(content)

                if result[0] == "discarded":
                    continue
                elif result[0] == "title":
                    current_table = result[1]
                elif result[0] == "element":
                    [*table, key] = chain(current_table, result[1])
                    path = (".".join(table), key)
                    path2line[path] = LineNumber(line_number)
                else:
                    assert_never(result)

            except Err:
                break

            line_number += 1

        return cls(
            data=data,
            path2line=path2line,
        )
