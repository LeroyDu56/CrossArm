# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""SetSysData: the active tool, work object or load selected by a TP line.

    SetSysData tGlue;          UTOOL_NUM=3           (a tool past the limit: UTOOL[10]=PR[90], UTOOL_NUM=10)
    SetSysData wTable;         UFRAME_NUM=2
    SetSysData loPart;         PAYLOAD[8]            as GripLoad loPart: the schedule of the tool with that load

RAPID's moves name their tool and work object, so the active ones are what jogging, CRobT without a tool and
GetSysData see; on the FANUC the frames a program selects are the jogging ones too. GetSysData reads them from the
controller: a TP program reads no system variable on the measured controller (`R[n]=$MNUTOOLNUM[1]`, `$MNUFRAMENUM`,
`$PLST_PARNUM`, `$MSKKEY` load and stop the program with VARS-034, ROBOGUIDE V10.10, R-1000iA/80F), so it stays
TODO, saying so; so does OpMode(), the operating mode (unsupported.NO_TP).
"""

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

_KINDS = {"tooldata": ("UT", "UTOOL"), "wobjdata": ("UF", "UFRAME")}


class SystemData:
    """The routine translator's part that writes SetSysData (mixed into it)."""

    def set_sys_data(self, call: n.ProcCall) -> None:
        positional = [a.value for a in call.args if a.name is None]
        named = [a.name for a in call.args if a.name is not None]
        if named:
            raise Untranslatable(f"SetSysData \\{named[0]}: a data named at run time is not converted", Blocker.RUNTIME_FRAME)
        if len(positional) != 1 or not isinstance(positional[0], n.Name):
            raise Untranslatable("SetSysData: a tool, work object or load named in the line is converted", Blocker.RUNTIME_FRAME)
        data = positional[0]
        type_name = self.c.symbols.type_of(data.name)  # type: ignore[attr-defined]
        if type_name == "loaddata":
            self.grip_load(call, data)  # type: ignore[attr-defined]
            self.c.warn_once(f"setsysdata:{self.name}:{call.span.line}", self.name, call.span.line,  # type: ignore[attr-defined]
                             f"SetSysData {data.name}: the payload carried, as GripLoad {data.name}", Blocker.PAYLOAD)
            return
        if type_name not in _KINDS:
            raise Untranslatable(f"SetSysData {format_expr(data)}: a {type_name or 'data'} is not a tool, work object"
                                 " or load", Blocker.RUNTIME_FRAME)  # fmt: skip
        kind, resource = _KINDS[type_name]
        selected = self.c.selection(kind, self.c.frame_number(kind, data, self.name, call.span.line))  # type: ignore[attr-defined]
        number, bank = selected
        if bank is not None:  # above what the controller holds: loaded into the reserved number
            self.emit(f"{resource}[{number}]=PR[{bank}]")  # type: ignore[attr-defined]
        self.emit(f"{resource}_NUM={number}")  # type: ignore[attr-defined]
        if kind == "UT":
            self.active_ut, self.last_tool = selected, data
        else:
            self.active_uf = selected


__all__ = ["SystemData"]
