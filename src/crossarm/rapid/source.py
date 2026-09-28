# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Reading RAPID files from disk.

Real controller backups mix encodings: RobotWare 7 (.modx/.sysx) writes UTF-8,
older IRC5/S4C exports are often Windows-1252. Line endings are CRLF.
Everything downstream works on a decoded string with '\\n' line endings only.
"""

from dataclasses import dataclass
from pathlib import Path

_UTF8_BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    text: str  # decoded, newlines normalised to "\n"
    encoding: str  # "utf-8", "utf-8-sig" or "cp1252"


def decode(data: bytes) -> tuple[str, str]:
    """Decode raw bytes, returning (text, encoding_used). Never raises."""
    if data.startswith(_UTF8_BOM):
        return data[len(_UTF8_BOM):].decode("utf-8", errors="replace"), "utf-8-sig"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        # cp1252 leaves 5 byte values undefined; "replace" keeps the parser going.
        return data.decode("cp1252", errors="replace"), "cp1252"


def normalise_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_source(path: str | Path) -> SourceFile:
    raw = Path(path).read_bytes()
    text, encoding = decode(raw)
    return SourceFile(path=str(path), text=normalise_newlines(text), encoding=encoding)
