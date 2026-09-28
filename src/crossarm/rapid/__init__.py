# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""ABB RAPID front-end: read a .mod/.modx/.sys/.sysx file into a nodes.Module."""

from dataclasses import dataclass
from pathlib import Path

from crossarm.diagnostics import Diagnostic, Severity
from crossarm.rapid import nodes
from crossarm.rapid.parser import parse
from crossarm.rapid.source import normalise_newlines, read_source

RAPID_SUFFIXES = frozenset({".mod", ".modx", ".sys", ".sysx", ".prg"})


@dataclass(frozen=True, slots=True)
class ParseResult:
    path: str
    encoding: str
    module: nodes.Module | None
    diagnostics: tuple[Diagnostic, ...]
    text: str = ""  # decoded source, LF line endings

    @property
    def ok(self) -> bool:
        return self.module is not None and not any(d.severity is Severity.ERROR for d in self.diagnostics)


def parse_text(text: str, *, path: str = "<string>") -> ParseResult:
    text = normalise_newlines(text)
    module, diagnostics = parse(text)
    return ParseResult(path, "str", module, tuple(diagnostics), text)


def parse_file(path: str | Path) -> ParseResult:
    source = read_source(path)
    module, diagnostics = parse(source.text)
    return ParseResult(source.path, source.encoding, module, tuple(diagnostics), source.text)


__all__ = ["RAPID_SUFFIXES", "ParseResult", "nodes", "parse_file", "parse_text"]
