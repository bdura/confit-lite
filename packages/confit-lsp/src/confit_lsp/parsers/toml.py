from typing import Iterator
from persil import string, regex
from persil.result import Ok
from persil.utils import Span

from .utils import range_from_persil, whitespace
from .types import Element, Kind


dquote = string('"')
squote = string("'")
dot = string(".")
lbracket = string("[")
rbracket = string("]")
backslash = string("\\")
equal = string("=")


string_part = regex(r'[^"\\]+')
string_esc = backslash >> (
    backslash
    | string("/")
    | string('"')
    | string("b").result("\b")
    | string("f").result("\f")
    | string("n").result("\n")
    | string("r").result("\r")
    | string("t").result("\t")
    | regex(r"u[0-9a-fA-F]{4}").map(lambda s: chr(int(s[1:], 16)))
)

basic_string = (
    dquote >> (string_part | string_esc).many().map(lambda s: "".join(s)) << dquote
)
literal_string = squote >> regex(r"[^']+") << squote

toml_string = (basic_string | literal_string).desc("string")

bare_key = regex(r"[A-Za-z0-9_-]+")
quoted_key = toml_string
key = (bare_key | quoted_key).desc("key")

dotted_keys = key.sep_by(whitespace >> dot << whitespace).map(tuple).desc("dotted-key")

table_title = (lbracket >> dotted_keys.span() << rbracket).desc("title")

line_remainder = regex(r".*")

value = (toml_string | regex(r"[^\s]+")).desc("value")

key_value_pair = (
    dotted_keys.span()
    .combine(whitespace >> equal >> whitespace >> value.span())
    .desc("key-value")
)

element = (
    whitespace
    >> (
        key_value_pair.map(lambda v: ("kv", v))
        | table_title.map(lambda v: ("title", v))
    )
    << line_remainder
    << string("\n")
).desc("element")


def parse_toml(content: str) -> Iterator[tuple[Kind, Element]]:
    index = 0
    root = tuple[str, ...]()

    while isinstance(result := element.wrapped_fn(content, index), Ok):
        index = result.index

        match result.value:
            case ("title", span):
                root = span.value
                yield "key", Element(path=root, location=range_from_persil(span))
            case ("kv", (key, value)):
                path = root + key.value
                yield (
                    "key",
                    Element(
                        path=path,
                        location=range_from_persil(key),
                    ),
                )
                yield (
                    "value",
                    Element(
                        path=path,
                        location=range_from_persil(value),
                    ),
                )
