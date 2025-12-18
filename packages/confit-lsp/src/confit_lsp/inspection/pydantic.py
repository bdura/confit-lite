import inspect
from typing import Callable, Any, get_type_hints
from pydantic import BaseModel, ConfigDict, create_model


def get_pydantic_input_model(
    func: Callable,
) -> tuple[type[BaseModel], Any]:
    """
    Convert a function signature to a Pydantic model for input validation.

    Args:
        func: The function to inspect.

    Returns:
        A Pydantic model class representing the function's parameters.
    """
    sig = inspect.signature(func)

    try:
        type_hints = get_type_hints(func, include_extras=True)
    except Exception:
        type_hints = {}

    # Build field definitions for Pydantic model
    fields = {}

    for param_name, param in sig.parameters.items():
        # Get the type annotation
        param_type = type_hints.get(param_name, Any)

        # Handle default values
        if param.default is inspect.Parameter.empty:
            # Required field (no default)
            fields[param_name] = (param_type, ...)
        else:
            # Optional field with default
            fields[param_name] = (param_type, param.default)

    model = create_model(
        "InputModel",
        **fields,
        __config__=ConfigDict(arbitrary_types_allowed=True),
    )

    return model, type_hints.get("return")
