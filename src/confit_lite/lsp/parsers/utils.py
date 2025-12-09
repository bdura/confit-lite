from typing import Sequence
from lsprotocol.types import Position, Range
from persil import regex, Parser
from persil.utils import RowCol, Span

whitespace = regex(r"\s*")


def lexeme[In: Sequence, Out](p: Parser[In, Out]) -> Parser[In, Out]:
    return p << whitespace


def position_from_persil(persil: RowCol) -> Position:
    return Position(
        line=persil.row,
        character=persil.col,
    )


def range_from_persil(persil: Span) -> Range:
    return Range(
        start=position_from_persil(persil.start),
        end=position_from_persil(persil.stop),
    )
