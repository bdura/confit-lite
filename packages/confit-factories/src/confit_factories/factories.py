"""Built-in factories."""

from pydantic import HttpUrl
from confit_lite.registry import register


@register("test")
def test(
    a: float,
    other: int,
) -> float:
    """Add two numbers together."""
    return a + other


@register("add")
def add(
    a: float,
    other: float,
) -> float:
    """Add two numbers together."""
    return a + other


@register("multiply")
def multiply(
    a: float,
    b: float = 1.0,
) -> float:
    """Multiply two numbers together."""
    return a * b


@register("something-interesting")
def build_url(
    url: HttpUrl,
    retries: int = 0,
) -> float:
    """Build a URL.

    Just demonstrating how more complex type would work.
    """
    ...
