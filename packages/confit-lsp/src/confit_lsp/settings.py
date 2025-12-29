import re
from typing import Annotated, Callable, cast
from pydantic import PlainValidator
from importlib import import_module
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SettingsConfigDict,
)


OBJECT_PATH_PATTERN = re.compile(r"^_*[A-Za-z][A-Za-z0-9_]+$")


RawRegistry = Callable[[str], Callable | None]


def _validate_object_path(name: str) -> str:
    """Check that an individual name section is compatible with Python naming
    conventions."""

    if OBJECT_PATH_PATTERN.match(name):
        return name
    raise ValueError(f"Object name is incompatible with Python object: {name}")


def _extract_registry(path: str) -> RawRegistry:
    if path.count(":") != 1:
        raise ValueError("There should be exactly one colon.")

    module_path, element_path = path.split(":")
    attr_chain = [_validate_object_path(name) for name in element_path.split(".")]

    if not attr_chain:
        raise ValueError("Cannot be a module")

    # Import the module
    module = import_module(module_path)

    # Navigate the attribute chain
    obj = module
    for attr in attr_chain:
        obj = getattr(obj, attr)

    if not callable(obj):
        raise ValueError("Supplied element should be callable.")

    return cast(RawRegistry, obj)


def validate_registry(factory: str | RawRegistry) -> RawRegistry:
    if callable(factory):
        return factory
    return _extract_registry(factory)


Registry = Annotated[RawRegistry, PlainValidator(validate_registry)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        pyproject_toml_table_header=("tool", "confit"),
    )

    factories: dict[str, Registry] = dict()

    def __getitem__(self, item) -> Registry:
        return self.factories[item]

    def get(self, item) -> Registry | None:
        return self.factories.get(item)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (PyprojectTomlConfigSettingsSource(settings_cls),)
