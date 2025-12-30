"""
TOML LSP Server with element validation and hover support.
"""

from functools import cached_property
import logging
from typing import Any, Optional

from pydantic import TypeAdapter, ValidationError
from pygls.lsp.server import LanguageServer
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    INITIALIZE,
    TEXT_DOCUMENT_HOVER,
    TEXT_DOCUMENT_DEFINITION,
    TEXT_DOCUMENT_INLAY_HINT,
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    Diagnostic,
    DiagnosticSeverity,
    InlayHint,
    InlayHintKind,
    InlayHintParams,
    InsertTextFormat,
    PublishDiagnosticsParams,
    Hover,
    MarkupContent,
    MarkupKind,
    Location,
    HoverParams,
    DefinitionParams,
    InitializeParams,
)
from pygls.workspace import TextDocument
from confit_lite.registry import REGISTRY

from confit_lsp.settings import Registry, Settings

from .descriptor import ConfigurationView
from .parsers.types import ElementPath
from .capabilities import FunctionDescription


logging.basicConfig(
    filename="/tmp/config-lsp.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# In your server code
logger = logging.getLogger(__name__)
logger.info("LSP server started")


class ConfitLanguageServer(LanguageServer):
    """Language server for the Confit configuration system."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = Settings()
        self._views = dict[str, tuple[int, ConfigurationView]]()

    @property
    def registries(self) -> dict[str, Registry]:
        return self.settings.factories

    @cached_property
    def markers(self) -> set[str]:
        return set(self.registries.keys())

    def parse(
        self,
        text_document: TextDocument,
    ) -> ConfigurationView | None:
        uri = text_document.uri
        source = text_document.source
        source_hash = hash(source)

        if uri in self._views:
            h, view = self._views[uri]
            if h == source_hash:
                return view

        if not uri.endswith(".toml"):
            return None

        view = ConfigurationView.from_source(text_document.source)

        self._views[uri] = (source_hash, view)

        return view

    def validate_config(self, view: ConfigurationView) -> list[Diagnostic]:
        """Validate .toml and return diagnostics"""

        diagnostics = []

        roots = dict[ElementPath, ElementPath]()
        factories = dict[ElementPath, FunctionDescription]()

        for path in view.factories(self.markers):
            location = view.values[path]

            if path[:-1] in roots:
                diagnostics.append(
                    Diagnostic(
                        range=view.keys[path],
                        message="An object can reference a single factory element at most.",
                        severity=DiagnosticSeverity.Error,
                        source="confit-lsp",
                    )
                )
            else:
                roots[path[:-1]] = path

            factory_name = view.get_value(path)

            if not isinstance(factory_name, str):
                diagnostics.append(
                    Diagnostic(
                        range=location,
                        message=f"Element value must be a string, got {type(factory_name).__name__}",
                        severity=DiagnosticSeverity.Error,
                        source="confit-lsp",
                    )
                )
                continue

            if factory_name not in REGISTRY:
                diagnostics.append(
                    Diagnostic(
                        range=location,
                        message=f"Element '{factory_name}' not found in the registry.",
                        severity=DiagnosticSeverity.Error,
                        source="confit-lsp",
                    )
                )
                continue

            factories[path] = FunctionDescription.from_function(
                factory_name,
                REGISTRY[factory_name],
            )

        for path, factory in factories.items():
            root_path = path[:-1]
            root = view.get_object(root_path).copy()
            root_keys = set(root.keys()) - self.markers

            model_keys = set(factory.input_model.model_fields.keys())
            required_model_keys = set(
                key
                for key, info in factory.input_model.model_fields.items()
                if info.is_required()
            )

            extra_keys = root_keys - model_keys
            for key in extra_keys:
                diagnostics.append(
                    Diagnostic(
                        range=view.keys[(*root_path, key)],
                        message=f"Argument `{key}` is not recognized by `{factory.name}` and will be ignored.",
                        severity=DiagnosticSeverity.Warning,
                        source="confit-lsp",
                    )
                )

            factory_element = view.keys[path]
            missing_keys = required_model_keys - root_keys
            for key in missing_keys:
                diagnostics.append(
                    Diagnostic(
                        range=factory_element,
                        message=f"Argument `{key}` is missing.",
                        severity=DiagnosticSeverity.Error,
                        source="confit-lsp",
                    )
                )

            for key in root_keys & model_keys:
                info = factory.input_model.model_fields[key]
                value = root[key]

                total_path = (*root_path, key)

                target = view.references.get(total_path)

                if target is not None:
                    element = view.keys[total_path]
                    try:
                        view.get_value(target)
                    except KeyError:
                        diagnostics.append(
                            Diagnostic(
                                range=element,
                                message="No element with this key exists.",
                                severity=DiagnosticSeverity.Error,
                                source="confit-lsp",
                            )
                        )
                        continue
                    total_path = target

                subfactory_path = roots.get(total_path)
                if (
                    subfactory_path is not None
                    and (sub_factory_descriptor := factories.get(subfactory_path))
                    is not None
                ):
                    if sub_factory_descriptor.return_type is None:
                        continue
                    if info.annotation == Any:
                        continue

                    if sub_factory_descriptor.return_type != info.annotation:
                        diagnostics.append(
                            Diagnostic(
                                range=factory_element,
                                message=(
                                    f"Argument `{key}` is provided by a factory with incompatible type.\n"
                                    f"Expected `{info.annotation.__qualname__}`, got `{sub_factory_descriptor.return_type.__qualname__}`."
                                ),
                                severity=DiagnosticSeverity.Error,
                                source="confit-lsp",
                            )
                        )
                    continue

                try:
                    adapter = TypeAdapter(info.annotation)
                    adapter.validate_python(value)
                except ValidationError as e:
                    element = view.keys[total_path]
                    for error in e.errors():
                        msg = error["msg"]
                        diagnostics.append(
                            Diagnostic(
                                range=element,
                                message=f"Argument `{key}` has incompatible type.\n{msg}",
                                severity=DiagnosticSeverity.Error,
                                source="confit-lsp",
                            )
                        )

        return diagnostics


server = ConfitLanguageServer("confit-lsp", "v0.1")


@server.feature(INITIALIZE)
async def initialize(params: InitializeParams) -> None:
    """Initialize the server."""
    return


@server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls: ConfitLanguageServer, params: DidOpenTextDocumentParams):
    """Handle document open event"""

    doc = ls.workspace.get_text_document(params.text_document.uri)
    view = ls.parse(doc)

    if view is None:
        return

    diagnostics = ls.validate_config(view)
    payload = PublishDiagnosticsParams(
        uri=doc.uri,
        diagnostics=diagnostics,
    )
    ls.text_document_publish_diagnostics(payload)


@server.feature(TEXT_DOCUMENT_DID_SAVE)
async def did_save(ls: ConfitLanguageServer, params: DidSaveTextDocumentParams):
    """Handle document save event"""
    doc = ls.workspace.get_text_document(params.text_document.uri)
    view = ls.parse(doc)

    if view is None:
        return

    diagnostics = ls.validate_config(view)
    payload = PublishDiagnosticsParams(
        uri=doc.uri,
        diagnostics=diagnostics,
    )
    ls.text_document_publish_diagnostics(payload)


# @server.feature(TEXT_DOCUMENT_DID_CHANGE)
# async def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams):
#     """Handle document change event"""
#     doc = ls.workspace.get_text_document(params.text_document.uri)
#
#     if doc.uri.endswith(".toml"):
#         diagnostics = validate_config(doc)
#         payload = PublishDiagnosticsParams(
#             uri=doc.uri,
#             diagnostics=diagnostics,
#         )
#         ls.text_document_publish_diagnostics(payload)


@server.feature(TEXT_DOCUMENT_HOVER)
async def hover(ls: ConfitLanguageServer, params: HoverParams) -> Optional[Hover]:
    """Provide hover information for factories"""

    doc = ls.workspace.get_text_document(params.text_document.uri)
    view = ls.parse(doc)

    if view is None:
        return None

    cursor = params.position
    element = view.get_element_from_position(cursor)

    if element is None:
        return None

    _, path = element
    *path, key = path

    root = view.get_object(path)

    factory_name = root.get(key)

    if factory_name is None:
        return None

    factory = ls.registries[key](factory_name)

    if factory is None:
        return None

    description = FunctionDescription.from_function(factory_name, factory)

    if key in ls.markers:
        return Hover(
            contents=MarkupContent(
                kind=MarkupKind.Markdown,
                value=f"**Factory: {factory_name}**\n\n{description.docstring}",
            )
        )

    field_info = description.input_model.model_fields.get(key)

    if field_info is None:
        return None

    return Hover(
        contents=MarkupContent(
            kind=MarkupKind.Markdown,
            value=f"**Field: {key}**\n\n{field_info.annotation}",
        )
    )


@server.feature(TEXT_DOCUMENT_DEFINITION)
async def definition(
    ls: ConfitLanguageServer,
    params: DefinitionParams,
) -> Location | None:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    view = ls.parse(doc)

    if view is None:
        return None

    cursor = params.position
    element = view.get_element_from_position(cursor)

    match element:
        case ("value", path):
            pass
        case _:
            return None

    target = view.references.get(path)
    if target is not None:
        return Location(uri=doc.uri, range=view.keys[target])

    if path[-1] not in ls.markers:
        # TODO: go to the definition of the argument
        return None

    factory_name = view.get_value(path)

    if factory_name is None:
        return None

    factory = ls.registries[path[-1]](factory_name)

    if factory is None:
        return None

    description = FunctionDescription.from_function(factory_name, factory)

    return description.location


@server.feature(TEXT_DOCUMENT_COMPLETION)
async def completion(
    ls: ConfitLanguageServer,
    params: CompletionParams,
) -> Optional[CompletionList]:
    """Provide auto-completion for element values"""
    doc = ls.workspace.get_text_document(params.text_document.uri)
    view = ls.parse(doc)

    if view is None:
        return None

    cursor = params.position
    element = view.get_element_from_position(cursor)

    match element:
        case ("value", path):
            pass
        case _:
            return None

    *_, key = path

    if key != "factory":
        return None

    # Create completion items for all elements
    items = []
    for factory_name, factory in REGISTRY.items():
        description = FunctionDescription.from_function(factory_name, factory)

        docstring = description.docstring or "N/A"

        items.append(
            CompletionItem(
                label=factory_name,
                kind=CompletionItemKind.Value,
                detail=docstring[:50] + "..."
                if len(docstring) > 50
                else description.docstring,
                documentation=MarkupContent(
                    kind=MarkupKind.Markdown,
                    value=f"**{factory_name}**\n\n{description.docstring}",
                ),
                insert_text=f"{factory_name}",
                insert_text_format=InsertTextFormat.PlainText,
            )
        )

    return CompletionList(is_incomplete=False, items=items)


@server.feature(TEXT_DOCUMENT_INLAY_HINT)
def inlay_hints(
    ls: ConfitLanguageServer,
    params: InlayHintParams,
):
    doc = ls.workspace.get_text_document(params.text_document.uri)
    view = ls.parse(doc)

    if view is None:
        return None

    hints = list[InlayHint]()

    start = params.range.start
    end = params.range.end

    factories = dict[ElementPath, FunctionDescription]()
    for path in view.factories(ls.settings.factories.keys()):
        factory_name = view.get_value(path)
        factory = REGISTRY.get(factory_name)

        if factory is None:
            continue

        factories[path[:-1]] = FunctionDescription.from_function(factory_name, factory)

    for path, location in view.keys.items():
        if location.start > end or start > location.end:
            continue

        path, key = path[:-1], path[-1]

        if key in ls.markers:
            continue

        factory = factories.get(path)

        if factory is None:
            continue

        field_info = factory.input_model.model_fields.get(key)

        if field_info is None:
            continue

        annotation = getattr(field_info.annotation, "__name__", None)

        if annotation is None:
            annotation = field_info.annotation and str(field_info.annotation) or None

        if annotation is None:
            continue

        hints.append(
            InlayHint(
                label=f": {annotation}",
                kind=InlayHintKind.Type,
                padding_left=False,
                padding_right=False,
                position=location.end,
            )
        )

    return hints


def run():
    server.start_io()


if __name__ == "__main__":
    run()
