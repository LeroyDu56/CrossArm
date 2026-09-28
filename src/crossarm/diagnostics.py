# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Source positions and diagnostics shared by every parser/writer."""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class Span:
    """Position of a construct in the source file (1-based line and column)."""

    line: int
    col: int


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: Severity
    message: str
    span: Span

    def __str__(self) -> str:
        return f"{self.span.line}:{self.span.col}: {self.severity.value}: {self.message}"
