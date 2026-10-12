# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The RobotWare version and the options of an ABB backup, for `crossarm diagnose`.

Two places hold them; both are read, whichever is there:

    BACKINFO/backinfo.txt    RobotWare 6: the >>PRODUCTS_ID: section

        >>PRODUCTS_ID:
        RobotWare Version: 6.12.03
          709-1 DeviceNet Master/Slave
          623-1 Multitasking
          IRB 1600-10/1.45

    BACKINFO/system.xml      (or system.xml at the backup's top): an XML description of the system. Its exact layout
                             was not seen on a real backup, so it is read loosely: any element or attribute giving a
                             RobotWare version, and any text starting with an ABB option code (`616-1 PC Interface`).

Only public ABB vocabulary is kept: an option is kept when it starts with its ABB code (three or four digits, a dash,
one or two digits) followed by a short plain name; a robot when it is an IRB model. Everything else in these files
(the system's name, its serial number, paths, dates, languages) is ignored, and only counted for options without a
code. Nothing here raises: a file that cannot be read gives nothing.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

_VERSION = re.compile(r"\b(\d{1,2}\.\d{1,2}(?:\.\d{1,3}){0,2})\b")
_ROBOTWARE = re.compile(r"robotware|robotcontrol", re.IGNORECASE)
_OPTION = re.compile(r"^(\d{3,4}-\d{1,2})(?:\s+([A-Za-z][A-Za-z0-9 /&+.,()\-]{0,59}))?$")
_ROBOT = re.compile(r"^IRB\s?\d{2,5}[A-Za-z]?(?:[-/.]\d+(?:\.\d+)?)*[A-Za-z]?$")
_PRODUCTS = re.compile(r"^>>PRODUCTS_ID:\s*$")
_SECTION = re.compile(r"^>>\w+:")


@dataclass
class SystemInfo:
    robotware: str | None = None  # '6.12.03'
    options: list[str] = field(default_factory=list)  # '709-1 DeviceNet Master/Slave', sorted, no repeat
    robots: list[str] = field(default_factory=list)  # 'IRB 1600-10/1.45'
    other_lines: int = 0  # product lines not kept: options without a code, languages...
    sources: list[str] = field(default_factory=list)  # 'backinfo.txt', 'system.xml'


def _clean_option(text: str) -> str | None:
    text = " ".join(text.split())
    return text if _OPTION.match(text) else None


def _clean_robot(text: str) -> str | None:
    text = " ".join(text.split())
    return text if _ROBOT.match(text) else None


def _version(text: str) -> str | None:
    match = _VERSION.search(text)
    return match[1] if match else None


def read_backinfo(text: str, info: SystemInfo) -> None:
    lines = text.replace("\r\n", "\n").split("\n")
    inside = False
    for raw in lines:
        line = raw.strip()
        if _PRODUCTS.match(line):
            inside = True
            continue
        if _SECTION.match(line):
            inside = False
        if not inside or not line:
            continue
        if _ROBOTWARE.match(line) and ":" in line:
            info.robotware = info.robotware or _version(line.split(":", 1)[1])
        elif re.match(r"^\w[\w ]*version\s*:", line, re.IGNORECASE):
            continue  # RobotOS Version, Robots Version: not kept
        elif (option := _clean_option(line)) is not None:
            info.options.append(option)
        elif (robot := _clean_robot(line)) is not None:
            info.robots.append(robot)
        else:
            info.other_lines += 1


def read_system_xml(text: str, info: SystemInfo) -> None:
    if "<!DOCTYPE" in text or "<!ENTITY" in text:  # no entity expansion of any kind
        return
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return
    for element in root.iter():
        values = [value for value in element.attrib.values() if isinstance(value, str)]
        if element.text and element.text.strip():
            values.append(element.text.strip())
        names = " ".join([element.tag, *values])
        if info.robotware is None and _ROBOTWARE.search(names):
            for key, value in element.attrib.items():
                if "version" in key.lower() and (found := _version(value)):
                    info.robotware = found
        found = [option for option in map(_clean_option, (" ".join(values), *values)) if option is not None]
        if found:  # the fullest: name="608-1 World Zones" rather than id="608-1"
            info.options.append(max(found, key=len))
        elif element.tag.lower().endswith("option"):
            info.other_lines += 1


def read_system(root: Path | None) -> SystemInfo:
    """What the backup at `root` says of its system; an empty SystemInfo for loose files or nothing found."""
    info = SystemInfo()
    if root is None:
        return info
    backinfo = root / "BACKINFO" / "backinfo.txt"
    for path, reader in ((backinfo, read_backinfo), (root / "BACKINFO" / "system.xml", read_system_xml),
                         (root / "system.xml", read_system_xml)):  # fmt: skip
        try:
            if not path.is_file() or path.stat().st_size > 4_000_000:
                continue
            text = path.read_bytes().decode("utf-8", errors="replace").lstrip("﻿")
        except OSError:
            continue
        reader(text, info)
        info.sources.append(path.name)
    named = {option.split()[0] for option in info.options if " " in option}  # a code alone, named elsewhere: once
    info.options = sorted({option for option in info.options if " " in option or option not in named})
    info.robots = sorted(set(info.robots))
    return info
