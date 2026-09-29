# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""FANUC TP program model -> ASCII .LS text.

Layout sources (details in docs/fanuc_ls_format.md):

  CONFIRMED on controller exports:
    /PROG, /ATTR (tabs), /APPL, /MN, /POS, /END; CRLF line endings;
    "%4d:  instr ;" for instructions, "%4d:J P[1] 100% FINE    ;" for motions
    (motion letter right after the colon), "%4d:   ;" for an empty line;
    joint /POS block (UF/UT line then J1..J6 on two lines).

  CONFIRMED by a ROBOGUIDE round trip (load generated .LS, re-export):
    cartesian /POS block, two-line circular motion, IF/THEN, FOR, LBL/JMP, WAIT,
    and the "    ;" terminator of CALL and register assignments.
    Header fields computed by the controller (PROG_SIZE, MEMORY_SIZE) may be 0.
"""

import re
from datetime import datetime

from crossarm.fanuc.tp import Attributes, CartesianPosition, JointPosition, Motion, Program

CRLF = "\r\n"


def write_ls(program: Program) -> str:
    line_count = program.attributes.line_count
    kind = "Macro" if program.macro else "Cond" if program.condition else ""
    lines = _header(program.name, kind, program.attributes,
                    len(program.lines) if line_count is None else line_count)  # fmt: skip
    lines.append("/MN")
    for number, line in enumerate(program.lines, start=1):
        if isinstance(line, Motion):
            lines += _motion(number, line)
        elif not line.text:
            lines.append(f"{number:4d}:   ;")
        else:
            end = _terminator(line.text) if line.pad is None else " " * line.pad + ";"
            lines.append(f"{number:4d}:  {line.text}{end}")
    lines += program.mn_extra
    lines.append("/POS")
    for pos in program.positions:
        lines += _position(pos.number, pos.uf, pos.ut, pos.value)
    lines.append("/END")
    return CRLF.join(lines) + CRLF


# The controller pads some instructions before ';' (seen identically on older controllers'
# and ROBOGUIDE exports): calls, register assignments and waits on a condition. A call with
# arguments is not padded: `CALL NAME(1,2) ;` (ROBOGUIDE, argument probe). A position register set
# from a point, another register or the current position is, `PR[100]=P[17]    ;`, `PR[98]=PR[97]    ;`,
# `PR[51]=LPOS    ;`, and so are a component, `PR[95,3]=(-30)    ;`, and a register named by another,
# `PR[R[90]]=LPOS    ;`; but not one set from a frame, `PR[31]=UTOOL[1] ;`, nor a frame set from it,
# `UTOOL[1]=PR[100] ;` (ROBOGUIDE, probe programs as the controller stores them).
_PADDED = re.compile(r"^(CALL [^(]*$|R\[[^\]]*\]=|PR\[.*?\]=(?!UTOOL\[|UFRAME\[)|WAIT (DI|DO)\[|WAIT \()")


def _terminator(text: str) -> str:
    return "    ;" if _PADDED.match(text) else " ;"


def _num(value: float, width: int) -> str:
    """Controller number layout: 3 decimals, no leading zero below 1 ('.500', '-.000'),
    but an exact zero is written '0.000' (all observed on ROBOGUIDE exports).

    A negative zero is an exact zero too: without this, a converted axis such as
    -(J2 + J3) = -0.0 came out as '-0.000', a form no controller writes."""
    if value == 0:
        value = 0.0
    text = f"{value:.3f}"
    if value != 0:
        if text.startswith("0."):
            text = text[1:]
        elif text.startswith("-0."):
            text = "-" + text[2:]
    return text.rjust(width)


def _date(value: datetime) -> str:
    return value.strftime("DATE %y-%m-%d  TIME %H:%M:%S")


def _header(name: str, kind: str, attrs: Attributes, line_count: int) -> list[str]:
    modified = attrs.modified or attrs.created
    lines = [
        # tab + 2 spaces on all 8 real macros; a condition program is stored so too (ROBOGUIDE)
        f"/PROG  {name}" + (f"\t  {kind}" if kind else ""),
        "/ATTR",
        f"OWNER\t\t= {attrs.owner};",
        f'COMMENT\t\t= "{attrs.comment}";',
        f"PROG_SIZE\t= {attrs.prog_size};",
        f"CREATE\t\t= {_date(attrs.created)};",
        f"MODIFIED\t= {_date(modified)};",
        f"FILE_NAME\t= {attrs.file_name};",
        f"VERSION\t\t= {attrs.version};",
        f"LINE_COUNT\t= {line_count};",
        f"MEMORY_SIZE\t= {attrs.memory_size};",
        f"PROTECT\t\t= {attrs.protect};",
        f"TCD:  STACK_SIZE\t= {attrs.stack_size},",
        f"      TASK_PRIORITY\t= {attrs.task_priority},",
        f"      TIME_SLICE\t= {attrs.time_slice},",
        f"      BUSY_LAMP_OFF\t= {attrs.busy_lamp_off},",
        f"      ABORT_REQUEST\t= {attrs.abort_request},",
        f"      PAUSE_REQUEST\t= {attrs.pause_request};",
        f"DEFAULT_GROUP\t= {attrs.default_group};",
        f"CONTROL_CODE\t= {attrs.control_code};",
    ]
    if attrs.local_registers is not None:
        lines.append(f"LOCAL_REGISTERS\t= {attrs.local_registers};")
    if attrs.appl is not None:
        lines.append("/APPL")
        lines += attrs.appl
    return lines


def _motion(number: int, m: Motion) -> list[str]:
    options = f" {m.options}" if m.options else ""
    tail = f"{m.speed} {m.termination}{options}{'    ' if m.pad is None else ' ' * m.pad};"
    if m.kind == "C":
        if m.via is None:
            raise ValueError("circular motion needs a via point")
        # The end point goes on a continuation line without a number (confirmed by ROBOGUIDE).
        return [f"{number:4d}:C {m.via}    ", f"    :  {m.target} {tail}"]
    return [f"{number:4d}:{m.kind} {m.target} {tail}"]


def _position(number: int, uf: int, ut: int, value: CartesianPosition | JointPosition) -> list[str]:
    lines = [f"P[{number}]{{", "   GP1:"]
    if isinstance(value, JointPosition):
        j = [f"J{i}={_num(v, 10)} deg" for i, v in enumerate(value.joints, start=1)]
        lines += [
            f"\tUF : {uf}, UT : {ut},\t",
            "\t" + ",\t".join(j[:3]) + ",",
            "\t" + ",\t".join(j[3:]),
        ]
    else:
        v = value
        lines += [
            f"\tUF : {uf}, UT : {ut},\t\tCONFIG : '{v.config}',",
            f"\tX = {_num(v.x, 9)}  mm,\tY = {_num(v.y, 9)}  mm,\tZ = {_num(v.z, 9)}  mm,",
            f"\tW = {_num(v.w, 9)} deg,\tP = {_num(v.p, 9)} deg,\tR = {_num(v.r, 9)} deg",
        ]
    lines.append("};")
    return lines


__all__ = ["CRLF", "write_ls"]
