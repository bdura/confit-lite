import inspect
from typing import Callable, Any, get_type_hints
from pydantic import BaseModel, create_model


def get_pydantic_input_model(
    func: Callable,
) -> type[BaseModel]:
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

    # Create and return the Pydantic model
    return create_model("InputModel", **fields)
