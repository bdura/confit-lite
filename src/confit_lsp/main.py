"""
TOML LSP Server with element validation and hover support.
"""

import logging
from typing import Optional, Sequence

from pydantic import ValidationError
import tomlkit
from pygls.lsp.server import LanguageServer
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    TEXT_DOCUMENT_DID_CHANGE,
    INITIALIZE,
    TEXT_DOCUMENT_HOVER,
    TEXT_DOCUMENT_DEFINITION,
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    DidChangeTextDocumentParams,
    Diagnostic,
    DiagnosticSeverity,
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

from confit_lsp.descriptor import Data, LineNumber
from confit_lsp.registry import REGISTRY, Element
import logging


logging.basicConfig(
    filename="/tmp/config-lsp.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# In your server code
logger = logging.getLogger(__name__)
logger.info("LSP server started")

server = LanguageServer("config-lsp", "v0.1")


def find_key_positions(content: str, doc: tomlkit.TOMLDocument) -> list:
    """
    Find positions of 'factory' keys in the TOML document.
    Returns list of (line, col_start, col_end, value, path)
    """
    positions = []
    lines = content.split("\n")

    def visit_item(item, path="", section_line_offset=0):
        if isinstance(item, dict):
            for key, value in item.items():
                # Search for 'factory' key in current dict
                if key == "factory":
                    # Find the line containing this key
                    search_prefix = f"{path}." if path else ""
                    key_pattern = f"{key} ="

                    for line_idx, line in enumerate(lines):
                        if key_pattern in line:
                            col_start = line.find(key)
                            if col_start != -1:
                                col_end = col_start + len(key)
                                positions.append(
                                    {
                                        "line": line_idx,
                                        "col_start": col_start,
                                        "col_end": col_end,
                                        "value": value,
                                        "path": f"{path}.{key}" if path else key,
                                    }
                                )
                                break

                # Recursively visit nested structures
                new_path = f"{path}.{key}" if path else key
                visit_item(value, new_path)

    visit_item(doc)
    return positions


def get_key_value_offsets(
    line: str,
    key: str,
) -> tuple[
    tuple[int, int],
    tuple[int, int],
]:
    start_char = line.find(key)

    key_offset = start_char, start_char + len(key)

    start_char += line[start_char:].find("=") + 1
    start_char += len(line[start_char:]) - len(line[start_char:].lstrip())
    end_char = len(line.rstrip())

    value_offset = start_char, end_char

    return key_offset, value_offset


def validate_config(uri: str, content: str) -> list[Diagnostic]:
    """Validate config.toml and return diagnostics"""
    diagnostics = []
    lines = content.split("\n")

    try:
        data = Data.from_source(content)

        factory_paths = dict[str, Element]()

        for (path, key), line_number in data.path2line.items():
            if key != "factory":
                continue

            root = data.get_root(path)
            value = root[key]

            line = lines[line_number]
            _, (start_char, end_char) = get_key_value_offsets(line, key)

            element_range = Range(
                start=Position(line=line_number, character=start_char + 1),
                end=Position(line=line_number, character=end_char - 1),
            )

            if not isinstance(value, str):
                diagnostics.append(
                    Diagnostic(
                        range=element_range,
                        message=f"Element value must be a string, got {type(value).__name__}",
                        severity=DiagnosticSeverity.Error,
                        source="confit-lsp",
                    )
                )
                continue

            if value not in REGISTRY:
                diagnostics.append(
                    Diagnostic(
                        range=element_range,
                        message=f"Element '{value}' not found in the registry.",
                        severity=DiagnosticSeverity.Error,
                        source="confit-lsp",
                    )
                )
                continue

            factory_paths[path] = REGISTRY[value]

        for (path, key), line_number in data.path2line.items():
            if key == "factory":
                continue

            element = factory_paths.get(path)
            if element is None:
                continue

            line = lines[line_number]
            (start_char, end_char), _ = get_key_value_offsets(line, key)
            element_range = Range(
                start=Position(line=line_number, character=start_char),
                end=Position(line=line_number, character=end_char),
            )

            if key not in element.input_model.model_fields:
                diagnostics.append(
                    Diagnostic(
                        range=element_range,
                        message=f"Argument `{key}` does not exist for factory function `{element.name}`.",
                        severity=DiagnosticSeverity.Error,
                        source="confit-lsp",
                    )
                )

        for path, element in factory_paths.items():
            root = data.get_root(path)
            try:
                element.input_model.model_validate(root)
            except ValidationError as e:
                logger.debug(f"Pydantic error: {e}")
                for error in e.errors():
                    msg = error["msg"]

                    (key,) = error["loc"]
                    logger.debug(f"key: {repr(key)}")
                    logger.debug(f"msg: {repr(msg)}")

                    assert isinstance(key, str)

                    line_number = data.path2line.get((path, key))

                    if line_number is None:
                        logger.debug("key not found")
                        continue

                    line = lines[line_number]
                    _, (start_char, end_char) = get_key_value_offsets(line, key)
                    element_range = Range(
                        start=Position(line=line_number, character=start_char),
                        end=Position(line=line_number, character=end_char),
                    )

                    logger.debug(f"range: {repr(msg)}")

                    diagnostics.append(
                        Diagnostic(
                            range=element_range,
                            message=f"Argument `{key}` has incompatible type.\n{msg}",
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
        diagnostics = validate_config(doc.uri, doc.source)
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
        diagnostics = validate_config(doc.uri, doc.source)
        payload = PublishDiagnosticsParams(
            uri=doc.uri,
            diagnostics=diagnostics,
        )
        ls.text_document_publish_diagnostics(payload)


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
async def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams):
    """Handle document change event"""
    doc = ls.workspace.get_text_document(params.text_document.uri)

    if doc.uri.endswith("config.toml"):
        diagnostics = validate_config(doc.uri, doc.source)
        payload = PublishDiagnosticsParams(
            uri=doc.uri,
            diagnostics=diagnostics,
        )
        ls.text_document_publish_diagnostics(payload)


@server.feature(TEXT_DOCUMENT_HOVER)
async def hover(ls: LanguageServer, params: HoverParams) -> Optional[Hover]:
    """Provide hover information for factories"""

    doc = ls.workspace.get_text_document(params.text_document.uri)
    data = Data.from_source(doc.source)

    if not doc.uri.endswith("config.toml"):
        return None

    try:
        cursor_line = params.position.line

        result = data.line2path.get(LineNumber(cursor_line))

        if result is None:
            return None

        path, key = result

        root = data.data

        for k in path.split("."):
            root = root[k]

        factory = root.get("factory")

        if factory is None:
            return None

        element = REGISTRY.get(factory)

        if element is None:
            return None

        if key == "factory":
            return Hover(
                contents=MarkupContent(
                    kind=MarkupKind.Markdown,
                    value=f"**Factory: {factory}**\n\n{element.docstring}\n\n"
                    + "\n".join(
                        (
                            f"- {field_name}\n"
                            for field_name in element.input_model.model_fields.keys()
                        )
                    ),
                )
            )

        field_info = element.input_model.model_fields.get(key)

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

    if not doc.uri.endswith("config.toml"):
        return None

    try:
        toml_doc = tomlkit.parse(doc.source)
        positions = find_key_positions(doc.source, toml_doc)

        cursor_line = params.position.line

        for pos in positions:
            if pos["line"] == cursor_line:
                value = pos["value"]

                if (
                    isinstance(value, str)
                    and (element := REGISTRY.get(value)) is not None
                ):
                    return element.location

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
        if "element" in current_line and "=" in current_line:
            # Create completion items for all elements
            items = []
            for key, element in REGISTRY.items():
                items.append(
                    CompletionItem(
                        label=key,
                        kind=CompletionItemKind.Value,
                        detail=element.docstring[:50] + "..."
                        if len(element.docstring) > 50
                        else element.docstring,
                        documentation=MarkupContent(
                            kind=MarkupKind.Markdown,
                            value=f"**{key}**\n\n{element.docstring}",
                        ),
                        insert_text=f'"{key}"',
                        insert_text_format=InsertTextFormat.PlainText,
                    )
                )

            return CompletionList(is_incomplete=False, items=items)

    except Exception as e:
        logger.error(f"Error in completion: {e}")

    return None


def run():
    server.start_io()


if __name__ == "__main__":
    run()
