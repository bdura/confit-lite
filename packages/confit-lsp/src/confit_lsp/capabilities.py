from dataclasses import dataclass
from typing import Callable, Self


from lsprotocol.types import Location
from pydantic import BaseModel

from .inspection import get_function_location, get_pydantic_input_model


@dataclass
class FunctionDescription:
    name: str
    location: Location
    input_model: type[BaseModel]
    docstring: str | None

    @classmethod
    def from_function(
        cls,
        name: str,
        func: Callable,
    ) -> Self:
        location = get_function_location(func)
        input_model = get_pydantic_input_model(func)
        docstring = func.__doc__

        return cls(
            name=name,
            docstring=docstring,
            location=location,
            input_model=input_model,
        )
