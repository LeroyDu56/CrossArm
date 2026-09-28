# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""ABB I/O configuration (SYSPAR/EIO.cfg): signal names and types.

Only the EIO_SIGNAL section is read. Record layout (RobotWare 6/7):

    EIO_SIGNAL:

          -Name "doGrip" -SignalType "DO" -Device "d652"\\
          -Label "Gripper close" -DeviceMap "3"

Records are separated by blank lines, a trailing backslash continues a line.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from crossarm.rapid.source import read_source

_ATTRIBUTE = re.compile(r'-(\w+)\s+(?:"([^"]*)"|(\S+))')
_SECTION = re.compile(r"^([A-Z][A-Z0-9_]*):\s*$")


@dataclass(frozen=True, slots=True)
class Signal:
    name: str
    signal_type: str  # DI, DO, GI, GO, AI, AO
    device: str = ""
    device_map: str = ""
    label: str = ""


def parse_eio(text: str) -> dict[str, Signal]:
    """Signals by upper-cased name."""
    signals: dict[str, Signal] = {}
    section = ""
    record: list[str] = []

    def flush() -> None:
        if section == "EIO_SIGNAL" and record:
            attrs = {m[1]: m[2] if m[2] is not None else m[3] for m in _ATTRIBUTE.finditer(" ".join(record))}
            if "Name" in attrs and "SignalType" in attrs:
                signal = Signal(
                    attrs["Name"], attrs["SignalType"].upper(),
                    attrs.get("Device", ""), attrs.get("DeviceMap", ""), attrs.get("Label", ""),
                )  # fmt: skip
                signals[signal.name.upper()] = signal
        record.clear()

    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        header = _SECTION.match(line)
        if header:
            flush()
            section = header[1]
        elif not line:
            flush()
        elif not line.startswith("#"):
            record.append(line.rstrip("\\"))
    flush()
    return signals


def read_eio(path: str | Path) -> dict[str, Signal]:
    return parse_eio(read_source(path).text)


def find_eio(paths: list[Path]) -> Path | None:
    """EIO.cfg inside the given folders, or in a SYSPAR folder next to them (backup layout)."""
    for path in paths:
        folder = path if path.is_dir() else path.parent
        for candidate in (*folder.rglob("EIO.cfg"), *folder.parent.glob("SYSPAR/EIO.cfg")):
            return candidate
    return None
