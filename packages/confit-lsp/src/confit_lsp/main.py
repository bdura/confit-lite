"""
TOML LSP Server with element validation and hover support.
"""

import logging
from typing import Optional

from pydantic import ValidationError
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

from .descriptor import ConfigurationView
from .parsers.types import Element, ElementPath
from .capabilities import FunctionDescription


logging.basicConfig(
    filename="/tmp/config-lsp.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# In your server code
logger = logging.getLogger(__name__)
logger.info("LSP server started")

server = LanguageServer("confit-lsp", "v0.1")


def validate_config(doc: TextDocument) -> list[Diagnostic]:
    """Validate .toml and return diagnostics"""
    content = doc.source

    diagnostics = []

    try:
        view = ConfigurationView.from_source(content)

        factories = dict[ElementPath, FunctionDescription]()

        for element in view.elements:
            *path, key = element.path

            if key != "factory":
                continue

            root = view.get_object(path)
            factory_name = root[key]

            if not isinstance(factory_name, str):
                diagnostics.append(
                    Diagnostic(
                        range=element.value,
                        message=f"Element value must be a string, got {type(factory_name).__name__}",
                        severity=DiagnosticSeverity.Error,
                        source="confit-lsp",
                    )
                )
                continue

            if factory_name not in REGISTRY:
                diagnostics.append(
                    Diagnostic(
                        range=element.value,
                        message=f"Element '{factory_name}' not found in the registry.",
                        severity=DiagnosticSeverity.Error,
                        source="confit-lsp",
                    )
                )
                continue

            factories[tuple(path)] = FunctionDescription.from_function(
                factory_name,
                REGISTRY[factory_name],
            )

        for element in view.elements:
            path = element.path
            key = path[-1]

            if key == "factory":
                continue

            factory = factories.get(path)
            if factory is None:
                continue

            if key not in factory.input_model.model_fields:
                diagnostics.append(
                    Diagnostic(
                        range=element.key,
                        message=f"Argument `{key}` does not exist for factory function `{factory.name}`.",
                        severity=DiagnosticSeverity.Error,
                        source="confit-lsp",
                    )
                )

        for path, factory in factories.items():
            root = view.get_object(path).copy()

            extra_keys = (
                set(root.keys())
                - {"factory"}
                - set(factory.input_model.model_fields.keys())
            )

            for key in extra_keys:
                diagnostics.append(
                    Diagnostic(
                        range=view.path2element[(*path, key)].key,
                        message=f"Argument `{key}` is not recognized by `{factory.name}` and will be ignored.",
                        severity=DiagnosticSeverity.Warning,
                        source="confit-lsp",
                    )
                )

            try:
                factory.input_model.model_validate(root)
            except ValidationError as e:
                for error in e.errors():
                    msg = error["msg"]

                    (key,) = error["loc"]

                    assert isinstance(key, str)

                    element = view.path2element.get((*path, key))

                    if element is not None:
                        diagnostics.append(
                            Diagnostic(
                                range=element.value,
                                message=f"Argument `{key}` has incompatible type.\n{msg}",
                                severity=DiagnosticSeverity.Error,
                                source="confit-lsp",
                            )
                        )
                    else:
                        element = view.path2element[(*path, "factory")]
                        diagnostics.append(
                            Diagnostic(
                                range=element.key,
                                message=f"Argument `{key}` is missing.\n{msg}",
                                severity=DiagnosticSeverity.Error,
                                source="confit-lsp",
                            )
                        )

    except Exception as e:
        logger.error(f"Error validating document: {e}")

    return diagnostics


@server.feature(INITIALIZE)
async def initialize(params: InitializeParams) -> None:
    """Initialize the server."""
    return


@server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls: LanguageServer, params: DidOpenTextDocumentParams):
    """Handle document open event"""
    doc = ls.workspace.get_text_document(params.text_document.uri)

    if doc.uri.endswith(".toml"):
        diagnostics = validate_config(doc)
        payload = PublishDiagnosticsParams(
            uri=doc.uri,
            diagnostics=diagnostics,
        )
        ls.text_document_publish_diagnostics(payload)


@server.feature(TEXT_DOCUMENT_DID_SAVE)
async def did_save(ls: LanguageServer, params: DidSaveTextDocumentParams):
    """Handle document save event"""
    doc = ls.workspace.get_text_document(params.text_document.uri)

    # Validate .toml
    if doc.uri.endswith(".toml"):
        diagnostics = validate_config(doc)
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
async def hover(ls: LanguageServer, params: HoverParams) -> Optional[Hover]:
    """Provide hover information for factories"""

    doc = ls.workspace.get_text_document(params.text_document.uri)

    if not doc.uri.endswith(".toml"):
        return None

    try:
        view = ConfigurationView.from_source(doc.source)

        cursor = params.position
        element = view.get_element_from_position(cursor)

        if element is None:
            return None

        *path, key = element.path
        root = view.get_object(path)

        factory_name = root.get("factory")

        if factory_name is None:
            return None

        factory = REGISTRY.get(factory_name)

        if factory is None:
            return None

        description = FunctionDescription.from_function(factory_name, factory)

        if key == "factory":
            return Hover(
                contents=MarkupContent(
                    kind=MarkupKind.Markdown,
                    value=f"**Factory: {factory_name}**\n\n{description.docstring}\n\n"
                    + "\n".join(
                        (
                            f"- {field_name}\n"
                            for field_name in description.input_model.model_fields.keys()
                        )
                    ),
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

    except Exception as e:
        logger.error(f"Error in hover: {e}")

    return None


@server.feature(TEXT_DOCUMENT_DEFINITION)
async def definition(
    ls: LanguageServer, params: DefinitionParams
) -> Optional[Location]:
    doc = ls.workspace.get_text_document(params.text_document.uri)

    if not doc.uri.endswith(".toml"):
        return None

    try:
        view = ConfigurationView.from_source(doc.source)

        cursor = params.position
        element = view.get_element_from_position(cursor)

        if element is None:
            return None

        *path, _ = element.path
        root = view.get_object(path)

        factory_name = root.get("factory")

        if factory_name is None:
            return None

        factory = REGISTRY.get(factory_name)

        if factory is None:
            return None

        description = FunctionDescription.from_function(factory_name, factory)

        return description.location

    except Exception as e:
        logger.error(f"Error in definition: {e}")

    return None


@server.feature(TEXT_DOCUMENT_COMPLETION)
async def completion(
    ls: LanguageServer,
    params: CompletionParams,
) -> Optional[CompletionList]:
    """Provide auto-completion for element values"""
    doc = ls.workspace.get_text_document(params.text_document.uri)

    if not doc.uri.endswith(".toml"):
        return None

    try:
        view = ConfigurationView.from_source(doc.source)

        cursor = params.position
        element = view.get_element_from_position(cursor)

        if element is None:
            return None

        *_, key = element.path

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

    except Exception as e:
        logger.error(f"Error in completion: {e}")

    return None


@server.feature(TEXT_DOCUMENT_INLAY_HINT)
def inlay_hints(params: InlayHintParams):
    document_uri = params.text_document.uri
    document = server.workspace.get_text_document(document_uri)

    try:
        view = ConfigurationView.from_source(document.source)
    except Exception as e:
        logger.error(f"Error in inlay hints: {e}")
        return None

    hints = list[InlayHint]()

    start_line = params.range.start.line
    end_line = params.range.end.line

    factories = dict[ElementPath, FunctionDescription]()
    for element in view.elements:
        if element.path[-1] != "factory":
            continue
        factory_name = view.get_value(element.path)
        factory = REGISTRY.get(factory_name)

        if factory is None:
            continue

        factories[element.path[:-1]] = FunctionDescription.from_function(
            factory_name, factory
        )

    elements = list[Element]()
    for element in view.elements:
        if element.path[-1] == "factory":
            continue

        if element.path[:-1] not in factories:
            continue

        if end_line <= element.key.start.line or element.value.end.line <= start_line:
            continue

        elements.append(element)

    for element in elements:
        key = element.path[-1]
        path = element.path[:-1]

        factory = factories[path]

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
                position=element.key.end,
            )
        )

    return hints


def run():
    server.start_io()


if __name__ == "__main__":
    run()
