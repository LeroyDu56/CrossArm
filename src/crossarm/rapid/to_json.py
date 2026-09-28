# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""AST -> JSON-ready dicts.

Generic over the dataclasses in nodes.py: every node becomes
{"node": "<ClassName>", "line": .., "col": .., <fields>...}, so adding a node
type never requires touching this file.
"""

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from crossarm.diagnostics import Diagnostic, Span


def to_data(obj: Any) -> Any:
    if isinstance(obj, Span):
        return {"line": obj.line, "col": obj.col}
    if isinstance(obj, Diagnostic):
        return {"severity": obj.severity.value, "message": obj.message, "line": obj.span.line, "col": obj.span.col}
    if is_dataclass(obj) and not isinstance(obj, type):
        out: dict[str, Any] = {"node": type(obj).__name__}
        for f in fields(obj):
            value = getattr(obj, f.name)
            if isinstance(value, Span):
                out["line"], out["col"] = value.line, value.col
            else:
                out[f.name] = to_data(value)
        return out
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (tuple, list)):
        return [to_data(item) for item in obj]
    return obj


def result_to_data(result: Any) -> dict[str, Any]:
    """Serialise a crossarm.rapid.ParseResult (file metadata + module + diagnostics)."""
    return {
        "file": result.path,
        "encoding": result.encoding,
        "diagnostics": to_data(result.diagnostics),
        "module": to_data(result.module),
    }


def dumps(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)
