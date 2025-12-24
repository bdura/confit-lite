from typing import Callable
from pydantic import BaseModel, ConfigDict
import pytest

from confit_lsp.capabilities import FunctionDescription


class Model:
    pass


class Func1Model(BaseModel):
    pass


def func1() -> Model:
    return Model()


def func2(model: Model) -> str:
    return str(model)


class Func2Model(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: Model


@pytest.mark.parametrize(
    "func,input_model,return_type",
    [
        (func1, Func1Model, Model),
        (func2, Func2Model, str),
    ],
)
def test_func_types(
    func: Callable,
    input_model: type[BaseModel],
    return_type: type,
):
    descriptor = FunctionDescription.from_function(name="whatever", func=func)
    assert descriptor.input_model.model_fields.keys() == input_model.model_fields.keys()

    for field_name, field_info in descriptor.input_model.model_fields.items():
        field_info2 = input_model.model_fields[field_name]
        assert field_info.annotation == field_info2.annotation
        assert field_info.default == field_info2.default

    assert descriptor.return_type == return_type


def test_compatibility():
    descriptor1 = FunctionDescription.from_function(name="func1", func=func1)
    descriptor2 = FunctionDescription.from_function(name="func2", func=func2)

    assert (
        descriptor1.return_type
        == descriptor2.input_model.model_fields["model"].annotation
    )
