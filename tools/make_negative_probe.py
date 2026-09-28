# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the negative-constant probe: how does a .LS file write -2.5 so that a controller loads it?

`CALL ARGRECORD(3,-2.5,1,1)` was refused by ROBOGUIDE (ASBN-092 Undefined instruction, at the
digit after the minus sign), and no .LS written by a controller in this repository holds a
negative constant. Each program here tries one way of writing one in one place; load them all,
then the controller's error log (/md/ERRALL.LS) says which ones it refused. Load only: nothing
here needs to run.

Usage:  python tools/make_negative_probe.py [output_dir]   (default tests/fixtures/probes/negative)
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program

# program name -> its lines. A = parentheses, B = bare minus; the same pair in each place.
VARIANTS = {
    "NEG_ASSIGN_A": ["R[20]=(-2.5)"],
    "NEG_ASSIGN_B": ["R[20]=-2.5"],
    "NEG_ARITH_A": ["R[20]=R[21]*(-2)"],
    "NEG_ARITH_B": ["R[20]=R[21]*-2"],
    "NEG_IF_A": ["IF (R[20]<(-2.5)) THEN", "R[21]=0", "ENDIF"],
    "NEG_IF_B": ["IF (R[20]<-2.5) THEN", "R[21]=0", "ENDIF"],
    "NEG_CALL_A": ["CALL ARGTURN((-2.5))"],
    "NEG_CALL_R": ["R[20]=0", "R[20]=R[20]-2.5", "CALL ARGTURN(R[20])"],  # the fallback: through a register
    "NEG_FOR_A": ["FOR R[20]=(-2) TO 2", "R[21]=0", "ENDFOR"],
    "NEG_FOR_B": ["FOR R[20]=-2 TO 2", "R[21]=0", "ENDFOR"],
    "NEG_WAIT_A": ["WAIT (R[20]<(-2.5))"],
    "NEG_WAIT_B": ["WAIT (R[20]<-2.5)"],
}


def programs() -> list[Program]:
    stamp = datetime(2026, 1, 1)
    return [Program(name, [Instruction(f"!negative probe {name[4:]}"), *map(Instruction, lines)], [],
                    Attributes(comment="negative probe", created=stamp)) for name, lines in VARIANTS.items()]  # fmt: skip


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests/fixtures/probes/negative"
    out.mkdir(parents=True, exist_ok=True)
    for program in programs():
        (out / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
        print(f"{program.name}.LS")


if __name__ == "__main__":
    main()
