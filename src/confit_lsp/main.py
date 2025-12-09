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
    TEXT_DOCUMENT_DID_CHANGE,
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
    DidChangeTextDocumentParams,
    Diagnostic,
    DiagnosticSeverity,
    InlayHint,
    InlayHintKind,
    InlayHintParams,
    InsertTextFormat,
    Position,
    PublishDiagnosticsParams,
    Range,
    Hover,
    MarkupContent,
    MarkupKind,
    Location,
    HoverParams,
    DefinitionParams,
    InitializeParams,
)
from pygls.workspace import TextDocument

from confit_lsp.descriptor import ConfigurationView
from confit_lsp.parsers.types import Element, ElementPath
from confit_lsp.registry import REGISTRY
from confit_lsp.capabilities import FunctionDescription


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
    """Validate config.toml and return diagnostics"""
    content = doc.source

    diagnostics = []

    try:
        data = ConfigurationView.from_source(content)

        factories = dict[ElementPath, FunctionDescription]()

        for element in data.elements:
            *path, key = element.path

            if key != "factory":
                continue

            root = data.get_object(path)
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

        for element in data.elements:
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
            root = data.get_object(path).copy()

            extra_keys = (
                set(root.keys())
                - {"factory"}
                - set(factory.input_model.model_fields.keys())
            )

            for key in extra_keys:
                diagnostics.append(
                    Diagnostic(
                        range=data.path2element[(*path, key)].key,
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

                    element = data.path2element.get((*path, key))

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
                        element = data.path2element[(*path, "factory")]
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

    if doc.uri.endswith("config.toml"):
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

    # Validate config.toml
    if doc.uri.endswith("config.toml"):
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
#     if doc.uri.endswith("config.toml"):
#         diagnostics = validate_config(doc)
#         payload = PublishDiagnosticsParams(
#             uri=doc.uri,
#             diagnostics=diagnostics,
#         )
#         ls.text_document_publish_diagnostics(payload)


# @server.feature(TEXT_DOCUMENT_HOVER)
async def hover(ls: LanguageServer, params: HoverParams) -> Optional[Hover]:
    """Provide hover information for factories"""

    doc = ls.workspace.get_text_document(params.text_document.uri)

    if not doc.uri.endswith("config.toml"):
        return None

    try:
        data = ConfigurationView.from_source(doc.source)

        cursor = params.position

        result = data.line2path.get(LineNumber(cursor_line))

        if result is None:
            return None

        path, key = result

        root = data.get_root(path)
        factory_name = root.get("factory")

        if factory_name is None:
            return None

        factory = REGISTRY.get(factory_name)

        if factory is None:
            return None

        desctiption = FunctionDescription.from_function(factory_name, factory)

        if key == "factory":
            return Hover(
                contents=MarkupContent(
                    kind=MarkupKind.Markdown,
                    value=f"**Factory: {factory_name}**\n\n{desctiption.docstring}\n\n"
                    + "\n".join(
                        (
                            f"- {field_name}\n"
                            for field_name in desctiption.input_model.model_fields.keys()
                        )
                    ),
                )
            )

        field_info = desctiption.input_model.model_fields.get(key)

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


# @server.feature(TEXT_DOCUMENT_DEFINITION)
async def definition(
    ls: LanguageServer, params: DefinitionParams
) -> Optional[Location]:
    doc = ls.workspace.get_text_document(params.text_document.uri)

    if not doc.uri.endswith("config.toml"):
        return None

    try:
        data = Data.from_source(doc.source)

        result = data.line2path.get(LineNumber(params.position.line))

        if result is None:
            return None

        path, key = result

        if key != "factory":
            return None

        line = doc.source.split("\n")[params.position.line]
        _, (start_char, end_char) = get_key_value_offsets(line, key)

        if not (start_char <= params.position.character <= end_char):
            return None

        root = data.get_root(path)
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

    if not doc.uri.endswith("config.toml"):
        return None

    try:
        lines = doc.source.split("\n")
        cursor_line = params.position.line

        if cursor_line >= len(lines):
            return None

        current_line = lines[cursor_line]

        # Check if we're on an `element =` line
        if "factory" in current_line and "=" in current_line:
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
                        insert_text=f'"{factory_name}"',
                        insert_text_format=InsertTextFormat.PlainText,
                    )
                )

            return CompletionList(is_incomplete=False, items=items)

    except Exception as e:
        logger.error(f"Error in completion: {e}")

    return None


# @server.feature(TEXT_DOCUMENT_INLAY_HINT)
def inlay_hints(params: InlayHintParams):
    items = []
    document_uri = params.text_document.uri
    document = server.workspace.get_text_document(document_uri)

    start_line = params.range.start.line
    end_line = params.range.end.line

    lines = document.lines[start_line : end_line + 1]

    data = Data.from_source(document.source)
    path_to_element = dict[str, FunctionDescription]()

    for (path, key), _ in data.path2line.items():
        if key != "factory":
            continue
        root = data.get_root(path)
        factory_name = root["factory"]

        factory = REGISTRY.get(factory_name)

        if factory is None:
            return None

        path_to_element[path] = FunctionDescription.from_function(factory_name, factory)

    for lineno, line in enumerate(lines):
        full_key = data.line2path.get(LineNumber(lineno + start_line))
        if full_key is None:
            continue

        path, key = full_key

        if key == "factory":
            continue

        factory = path_to_element.get(path)

        if factory is None:
            continue

        field_info = factory.input_model.model_fields.get(key)

        if field_info is None:
            continue

        (_, end_char), _ = get_key_value_offsets(line, key)

        annotation = getattr(field_info.annotation, "__name__", None)

        if annotation is None:
            annotation = field_info.annotation and str(field_info.annotation) or None

        if annotation is None:
            continue

        items.append(
            InlayHint(
                label=f": {annotation}",
                kind=InlayHintKind.Type,
                padding_left=False,
                padding_right=False,
                position=Position(line=lineno, character=end_char),
            )
        )

    return items


def run():
    server.start_io()


if __name__ == "__main__":
    run()
