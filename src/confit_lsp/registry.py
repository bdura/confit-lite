from typing import Callable, overload

from importlib.metadata import entry_points


REGISTRY = dict[str, Callable]()


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
        REGISTRY[name] = f
        return f

    if func is not None:
        return do_register(func)

    return do_register


def load_plugins() -> None:
    for plugin in entry_points(group="confit"):
        plugin.load()


load_plugins()
