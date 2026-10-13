# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""SetSysData: the active tool, work object or load selected by a TP line.

    SetSysData tGlue;          UTOOL_NUM=3           (a tool past the limit: UTOOL[10]=PR[90], UTOOL_NUM=10)
    SetSysData wTable;         UFRAME_NUM=2
    SetSysData loPart;         PAYLOAD[8]            as GripLoad loPart: the schedule of the tool with that load

RAPID's moves name their tool and work object, so the active ones are what jogging, CRobT without a tool and
GetSysData see; on the FANUC the frames a program selects are the jogging ones too. GetSysData reads them from the
controller: a TP program reads no system variable on the measured controller (`R[n]=$MNUTOOLNUM[1]`, `$MNUFRAMENUM`,
`$PLST_PARNUM`, `$MSKKEY` load and stop the program with VARS-034, ROBOGUIDE V10.10, R-1000iA/80F). Where a move
or SetSysData of the same routine selected the frame before it, CrossArm knows which: GetSysData is then the copy
of that frame (`tSaved := tGrip`, what an assignment of frames writes: `UTOOL[n]=PR[k]`, measured by the framefield
probe); elsewhere (the start of a routine, after a call) it stays TODO, saying so; so does OpMode(), the operating
mode (unsupported.NO_TP). GetSysData of a load: the PAYLOAD schedule selected stays, a remark and a warning.
"""

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.tp_numbers import ascii_text
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr


def _remark(text: str) -> str:
    from crossarm.convert.translate import REMARK_MAX

    return ("!" + ascii_text(text))[: REMARK_MAX + 1].rstrip()


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

    def get_sys_data(self, call: n.ProcCall) -> None:
        """GetSysData tCur: the active tool (work object) copied into tCur, when the line before selected it in
        this routine (`tCur := tGrip`, then what an assignment of frames writes); else TODO (VARS-034)."""
        positional = [a.value for a in call.args if a.name is None]
        if len(positional) != 1 or len(call.args) != 1 or not isinstance(positional[0], n.Name):
            raise Untranslatable("GetSysData: the active data read from the controller", Blocker.RUNTIME_FRAME)
        data = positional[0]
        type_name = (self.c.symbols.type_of(data.name) or "").lower()  # type: ignore[attr-defined]
        if type_name == "loaddata":
            self.emit(_remark(f"l.{call.span.line} GetSysData {data.name}"))  # type: ignore[attr-defined]
            self.c.warn_once(f"getsysdata:{self.name}:{call.span.line}", self.name, call.span.line,  # type: ignore[attr-defined]
                             f"GetSysData {data.name}: the load carried is the PAYLOAD schedule selected; {data.name}"
                             " keeps its saved value (a GripLoad of it selects that schedule)", Blocker.PAYLOAD)  # fmt: skip
            return
        if type_name not in _KINDS:
            raise Untranslatable(f"GetSysData {data.name}: not a tool, work object or load", Blocker.RUNTIME_FRAME)
        kind = _KINDS[type_name][0]
        active = self.active_ut if kind == "UT" else self.active_uf  # type: ignore[attr-defined]
        source = None if active is None else next(
            (info.rapid_name for (k, number), info in self.c.frames.items()  # type: ignore[attr-defined]
             if k == kind and self.c.selection(k, number) == active), None)  # type: ignore[attr-defined]  # fmt: skip
        if source is None:  # active at run time only: what the routine was called with
            raise Untranslatable(f"GetSysData {data.name}: the {'tool' if kind == 'UT' else 'work object'} active when"
                                 " the routine is called", Blocker.RUNTIME_FRAME)  # fmt: skip
        if source.upper() == data.name.upper():
            self.emit(_remark(f"l.{call.span.line} GetSysData {data.name}"))  # type: ignore[attr-defined]
            return
        self.assign(n.Assign(call.span, data, n.Name(call.span, source)))  # type: ignore[attr-defined]
        self.c.warn_once(f"getsysdata:{self.name}:{call.span.line}", self.name, call.span.line,  # type: ignore[attr-defined]
                         f"GetSysData {data.name}: the {'tool' if kind == 'UT' else 'work object'} selected before it"
                         f" in this routine is {source}: {data.name} := {source}", Blocker.RUNTIME_FRAME)  # fmt: skip


__all__ = ["SystemData"]
