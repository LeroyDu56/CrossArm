# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Which forms of TP instruction CrossArm writes, and which of them a controller has loaded.

Every instruction line is reduced to its form: numbers become `n`, register and label comments are
dropped, conditions keep their operators and operand kinds (`IF (DI[n]=OFF AND R[n]<n) THEN`). The
forms found in the programs given are compared with those of the .LS files in this repository that
were loaded on ROBOGUIDE (tests/fixtures/fanuc/roboguide_export and tests/fixtures/probes): what is
left has never been loaded on a controller, and is the next thing to probe.

Usage:  python tools/tp_forms.py <folder of .LS files> [...]
        (e.g. the output of a conversion; nothing is written)
"""

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.fanuc.ls_parser import LSFormatError, parse_ls
from crossarm.fanuc.tp import Instruction

ROOT = Path(__file__).resolve().parents[1]
VALIDATED = [ROOT / "tests/fixtures/fanuc/roboguide_export", ROOT / "tests/fixtures/probes"]


def form(text: str) -> str:
    """'IF (R[3:nSlot]<.5 AND DI[12]=ON) THEN' -> 'IF (R[n]<n AND DI[n]=ON) THEN'."""
    text = text.strip()
    if text.startswith("!"):
        return "!remark"
    if text.startswith("MESSAGE["):
        return "MESSAGE[text]"
    text = re.sub(r"\[(\d+):[^\]]*\]", r"[\1]", text)  # register / label comments
    text = re.sub(r"'[^']*'", "'s'", text)
    text = re.sub(r"\b(CALL|RUN) [A-Z0-9_]+", r"\1 PROG", text)
    text = re.sub(r"\[\d+\]", "[i]", text)
    text = re.sub(r"\[\d+,\d+\]", "[i,j]", text)
    text = re.sub(r"\(-\d*\.?\d+\)", "(-k)", text)  # a negative constant, in parentheses
    text = re.sub(r"(?<![A-Za-z0-9_.])-\d*\.?\d+(?![A-Za-z0-9_])", "-k", text)
    text = re.sub(r"(?<![A-Za-z0-9_.])\d+(?![A-Za-z0-9_.])", "k", text)  # integer
    text = re.sub(r"(?<![A-Za-z0-9_.])0\.\d+(?![A-Za-z0-9_])", "0.d", text)  # 0.5 and .5 kept apart
    text = re.sub(r"(?<![A-Za-z0-9_.])\d*\.\d+(?![A-Za-z0-9_])", "d", text)
    return text


def forms(folders: list[Path]) -> Counter[str]:
    found: Counter[str] = Counter()
    for folder in folders:
        for path in sorted(folder.rglob("*.LS")) + sorted(folder.rglob("*.ls")):
            try:
                program = parse_ls(path.read_bytes().decode("ascii", "replace"))
            except LSFormatError:
                continue
            for line in program.lines:
                if isinstance(line, Instruction):
                    found[form(line.text)] += 1
                else:
                    found[f"{line.kind} motion"] += 1
    return found


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    emitted = forms([Path(p) for p in sys.argv[1:]])
    validated = forms(VALIDATED)
    unknown = [(f, c) for f, c in emitted.most_common() if f not in validated]
    print(f"{len(emitted)} forms written, {len(emitted) - len(unknown)} loaded on ROBOGUIDE, {len(unknown)} never loaded:")
    for text, count in unknown:
        print(f"{count:6d}  {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
