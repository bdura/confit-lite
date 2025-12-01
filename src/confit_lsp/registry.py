from dataclasses import dataclass
from typing import Callable, overload

from lsprotocol.types import Location
from pydantic import BaseModel, HttpUrl

from .inspection import get_function_location, get_pydantic_input_model


@dataclass
class Element:
    name: str
    func: Callable
    location: Location
    input_model: type[BaseModel]

    @property
    def docstring(self) -> str:
        return self.func.__doc__ or "N/A"


REGISTRY = dict[str, Element]()


@overload
def register[F: Callable](name: str) -> Callable[[F], F]: ...


@overload
def register[F: Callable](
    name: str,
    func: F,
) -> F: ...


def register[F: Callable](
    name: str,
    func: F | None = None,
) -> Callable[[F], F] | F:
    def do_register(f: F) -> F:
        location = get_function_location(f)
        input_model = get_pydantic_input_model(f)

        element = Element(
            name=name,
            func=f,
            location=location,
            input_model=input_model,
        )

        REGISTRY[name] = element
        return f

    if func is not None:
        return do_register(func)

    return do_register


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
    b: float,
) -> float:
    """Multiply two numbers together."""
    return a * b


@register("something-interesting")
def something(
    a: float,
    b: HttpUrl,
) -> float:
    """Something random."""
    ...
