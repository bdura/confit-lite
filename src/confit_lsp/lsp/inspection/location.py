import inspect
from typing import Callable
from pathlib import Path

from lsprotocol.types import Location, Position, Range


def get_function_location(func: Callable) -> Location:
    """
    Get the location information of a function for LSP purposes.

    Args:
        func: The function to inspect

    Returns:
        Dictionary containing file path, line number, and column (0-indexed)
    """
    source_file = inspect.getsourcefile(func)
    if source_file is None:
        raise ValueError("Only proper functions can be annotated.")

    path = Path(source_file)

    source_lines, line_number = inspect.getsourcelines(func)

    n_lines = len(source_lines)
    [*_, last_line] = source_lines

    return Location(
        uri=path.as_uri(),
        range=Range(
            start=Position(line=line_number, character=0),
            end=Position(line=line_number + n_lines, character=len(last_line)),
        ),
    )
