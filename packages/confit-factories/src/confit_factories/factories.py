"""Built-in factories."""

from typing import Iterator
from pydantic import HttpUrl
from confit_lite.registry import register


@register("test")
def test(
    a: float,
    b: int,
    c: bool,
) -> float:
    """Test factory"""
    return a + b + c


@register("add")
def add(
    a: float,
    b: float,
) -> float:
    """Add two numbers together."""
    return a + b


@register("multiply")
def multiply(
    a: float,
    b: float = 1.0,
) -> float:
    """Multiply two numbers together."""
    return a * b


@register("url-builder")
def build_url(
    url: HttpUrl,
    retries: int = 0,
) -> str:
    """Build a URL.

    Just demonstrating how more complex type would work.
    """
    return ""


@register("counter")
class Counter:
    def __init__(
        self,
        start: int,
        step: int,
    ) -> None:
        """Counter."""
        self.count = start
        self.step = step

    def increment(self) -> None:
        self.count += self.step

    def __iter__(self) -> Iterator[int]:
        yield self.count
        self.increment()
