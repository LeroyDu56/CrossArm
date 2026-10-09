# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What TP has nothing for, or does otherwise: RAPID instructions, functions and data types a statement
using one stays TODO for, with why, as does a call to a routine of the backup using files or sockets, or given a byte
array its caller sends or receives, and the ERROR handler of such a routine; and RAPID's own instructions and data, which a backup never declares."""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping

from crossarm.convert.compute import path_of
from crossarm.convert.handlers import body as handler_body
from crossarm.convert.records import nodes
from crossarm.rapid import nodes as n
from crossarm.rapid.walk import split_params, walk_statements

# RAPID instructions, functions and data types TP has nothing for, by family: a statement using one is a TODO
# under Blocker.NO_TP_EQUIVALENT with why, rather than a call or a value CrossArm could not work out.
NO_TP_FAMILIES = {
    "files and serial channels: TP reads and writes no file": (
        "OPEN", "CLOSE", "WRITE", "WRITEBIN", "WRITEANYBIN", "WRITESTRBIN", "WRITERAWBYTES", "READANYBIN",
        "READRAWBYTES", "REWIND", "CLEARIOBUFF", "MAKEDIR", "REMOVEDIR", "REMOVEFILE", "RENAMEFILE",
        "COPYFILE", "OPENDIR", "CLOSEDIR", "READNUM", "READSTR", "READBIN", "READSTRBIN", "READDIR", "ISFILE",
        "FILESIZE", "FSSIZE", "IODEV", "DIR",
    ),
    "sockets: TP has no network messaging": (
        "SOCKETCREATE", "SOCKETCONNECT", "SOCKETSEND", "SOCKETRECEIVE", "SOCKETCLOSE", "SOCKETBIND",
        "SOCKETLISTEN", "SOCKETACCEPT", "SOCKETSENDTO", "SOCKETRECEIVEFROM", "SOCKETGETSTATUS", "SOCKETPEEK",
        "SOCKETDEV", "SOCKETSTATUS",
    ),
    "raw byte buffers: TP has none": (
        "PACKRAWBYTES", "UNPACKRAWBYTES", "CLEARRAWBYTES", "COPYRAWBYTES", "RAWBYTESLEN", "PACKDNHEADER",
        "RAWBYTES",
    ),
    "operator dialog waiting for an answer: TP shows a message, it does not ask the operator one": (
        "TPREADFK", "TPREADNUM", "TPREADDNUM", "UIMSGBOX", "UIMESSAGEBOX", "UINUMENTRY", "UINUMTUNE",
        "UIALPHAENTRY", "UILISTVIEW", "BTNRES",
    ),
    "a screen or an application of the ABB pendant: TP has none": ("TPSHOW", "UISHOW"),
    "the ABB event log and its error numbers: TP has none": ("ERRLOG", "BOOKERRNO", "ERRRAISE", "ERRWRITE"),
    "ABB system instruction (program modules, mechanical units): TP has none": (
        "SAVE", "LOAD", "UNLOAD", "STARTLOAD", "WAITLOAD", "ERASEMODULE",
        "ACTUNIT", "DEACTUNIT",
    ),
    # Measured: a TP program reads no system variable on the controller CrossArm was measured on (R[n]=$MNUTOOLNUM[1],
    # $MSKKEY... load, then stop it: VARS-034); SetSysData is converted (convert.system_data).
    "the active tool, work object or load read from the controller: a TP program reads no system variable (VARS-034"
    " Variable cannot be accessed, measured); select the frames by number where the RAPID selects them": ("GETSYSDATA",),
    "the operating mode (AUTO, T1, T2): a TP program reads no system variable (VARS-034, measured) and FANUC's"
    " standard UOP outputs do not give it; an output the robot is set up to give it on can be tested instead": (
        "OPMODE",
    ),
    "world zone: the FANUC sets zones up in its DCS or interference check menus, not in TP": (
        "WZBOXDEF", "WZCYLDEF", "WZSPHDEF", "WZHOMEJOINTDEF", "WZLIMJOINTDEF", "WZLIMSUP", "WZDOSET",
        "WZENABLE", "WZDISABLE", "WZFREE", "WZSTATIONARY", "WZTEMPORARY", "SHAPEDATA",
    ),
}  # fmt: skip
NO_TP = {name: why for why, names in NO_TP_FAMILIES.items() for name in names}
_SOCKETS = next(why for why in NO_TP_FAMILIES if why.startswith("sockets"))
# --karel converts files, not sockets: KAREL socket messaging talks through client tags (Cn:) set up on the robot,
# which a KAREL program cannot set itself; a socket statement stays TODO, saying so.
KAREL_SOCKETS = (f"{_SOCKETS}, and --karel does not convert them: KAREL socket messaging needs client tags configured"
                 " on the robot, which CrossArm does not set up")


def why_none(name: str, karel: bool = False) -> str:
    """Why TP has nothing for RAPID's instruction, function or data type `name` (upper case, in NO_TP); with
    --karel, sockets say that it does not convert them either."""
    why = NO_TP[name]
    return KAREL_SOCKETS if karel and why == _SOCKETS else why

# RAPID's error numbers for files, serial channels and sockets (any ERR_SOCK_... too): an ERROR handler testing only
# these, or errors of the backup raised only where files or sockets are used, handles what TP has nothing for.
FILE_SOCKET_ERRORS = frozenset({
    "ERR_FILEACC", "ERR_FILEEXIST", "ERR_FILEOPEN", "ERR_FILNOTFND", "ERR_DEV_MAXTIME", "ERR_RANYBIN_CHK",
    "ERR_RANYBIN_EOF", "ERR_RCVDATA",
})  # fmt: skip

# RAPID's own instructions (RobotWare 6 instruction reference): one the backup does not declare is not missing from
# it, CrossArm does not convert it. Any other routine nobody declares comes from a module or an option the backup
# does not hold.
RAPID_INSTRUCTIONS = frozenset({
    "ACCSET", "ACTEVENTBUFFER", "ACTUNIT", "ADD", "ALIASCAMERA", "ALIASIO", "ALIASIORESET", "BITCLEAR", "BITSET",
    "BOOKERRNO", "BREAK", "CALLBYVAR", "CAMFLUSH", "CAMGETPARAMETER", "CAMGETRESULT", "CAMLOADJOB", "CAMREQIMAGE",
    "CAMSETEXPOSURE", "CAMSETPARAMETER", "CAMSETPROGRAMMODE", "CAMSETRUNMODE", "CAMSTARTLOADJOB", "CAMWAITLOADJOB",
    "CANCELLOAD", "CHECKPROGREF", "CIRPATHMODE", "CLEAR", "CLEARIOBUFF", "CLEARPATH", "CLEARRAWBYTES", "CLKRESET",
    "CLKSTART", "CLKSTOP", "CLOSE", "CLOSEDIR", "CONFJ", "CONFL", "CONNECT", "COPYFILE", "COPYRAWBYTES", "CORRCLEAR",
    "CORRCON", "CORRDISCON", "CORRWRITE", "DEACTEVENTBUFFER", "DEACTUNIT", "DECR", "DITHERACT", "DITHERDEACT",
    "DROPSENSOR", "DROPWOBJ", "EGMACTJOINT", "EGMACTMOVE", "EGMACTPOSE", "EGMGETID", "EGMMOVEC", "EGMMOVEL",
    "EGMRESET", "EGMRUNJOINT", "EGMRUNPOSE", "EGMSETUPAI", "EGMSETUPAO", "EGMSETUPGI", "EGMSETUPLTAPP", "EGMSETUPUC",
    "EGMSTOP", "EGMSTREAMSTART", "EGMSTREAMSTOP", "EOFFSOFF", "EOFFSON", "EOFFSSET", "ERASEMODULE", "ERRLOG",
    "ERRRAISE", "ERRWRITE", "EXIT", "EXITCYCLE", "FRICIDEVALUATE", "FRICIDINIT", "FRICIDSETFRICLEVELS", "GETDATAVAL",
    "GETJOINTDATA", "GETSYSDATA", "GETTRAPDATA", "GRIPLOAD", "HOLLOWWRISTRESET", "IDELETE", "IDISABLE", "IENABLE",
    "IERROR", "INCR", "INDAMOVE", "INDCMOVE", "INDDMOVE", "INDRESET", "INDRMOVE", "INVERTDO", "IOBUSSTART",
    "IOBUSSTATE", "IODISABLE", "IOENABLE", "IPERS", "IRMQMESSAGE", "ISIGNALAI", "ISIGNALAO", "ISIGNALDI", "ISIGNALDO",
    "ISIGNALGI", "ISIGNALGO", "ISLEEP", "ITIMER", "IVARVALUE", "IWATCH", "LOAD", "LOADID", "MAKEDIR", "MANLOADIDPROC",
    "MECHUNITLOAD", "MOTIONPROCESSMODESET", "MOTIONSUP", "MOVEABSJ", "MOVEC", "MOVECDO", "MOVECSYNC", "MOVEEXTJ",
    "MOVEJ", "MOVEJDO", "MOVEJSYNC", "MOVEL", "MOVELDO", "MOVELSYNC", "MTOOLROTCALIB", "MTOOLTCPCALIB", "OPEN",
    "OPENDIR", "PACKDNHEADER", "PACKRAWBYTES", "PATHACCLIM", "PATHRECMOVEBWD", "PATHRECMOVEFWD", "PATHRECSTART",
    "PATHRECSTOP", "PATHRESOL", "PDISPOFF", "PDISPON", "PDISPSET", "PROCERRRECOVERY", "PULSEDO", "RAISETOUSER",
    "READANYBIN", "READBLOCK", "READCFGDATA", "READERRDATA", "READRAWBYTES", "REMOVEALLCYCLICBOOL",
    "REMOVECYCLICBOOL", "REMOVEDIR", "REMOVEFILE", "RENAMEFILE", "RESET", "RESETPPMOVED", "RESETRETRYCOUNT",
    "RESTOPATH", "REWIND", "RMQEMPTYQUEUE", "RMQFINDSLOT", "RMQGETMESSAGE", "RMQGETMSGDATA", "RMQGETMSGHEADER",
    "RMQREADWAIT", "RMQSENDMESSAGE", "RMQSENDWAIT", "SAVE", "SAVECFGDATA", "SCWRITE", "SEARCHC", "SEARCHEXTJ",
    "SEARCHJ", "SEARCHL", "SENDEVICE", "SET", "SETAO", "SETALLDATAVAL", "SETDATASEARCH", "SETDATAVAL", "SETDO",
    "SETGO", "SETLEADTHROUGH", "SETSYSDATA", "SINGAREA", "SKIPWARN", "SOCKETACCEPT", "SOCKETBIND", "SOCKETCLOSE",
    "SOCKETCONNECT", "SOCKETCREATE", "SOCKETLISTEN", "SOCKETRECEIVE", "SOCKETRECEIVEFROM", "SOCKETSEND",
    "SOCKETSENDTO", "SOFTACT", "SOFTDEACT", "SPEEDLIMAXIS", "SPEEDLIMCHECKPOINT", "SPEEDREFRESH", "SPYSTART",
    "SPYSTOP", "STARTLOAD", "STARTMOVE", "STARTMOVERETRY", "STCALIB", "STCLOSE", "STEPBWDPATH", "STINDGUN",
    "STINDGUNRESET", "STOOLROTCALIB", "STOOLTCPCALIB", "STOP", "STOPEN", "STOPMOVE", "STOPMOVERESET", "STOREPATH",
    "STTUNE", "STTUNERESET", "SUPSYNCSENSOROFF", "SUPSYNCSENSORON", "SYNCMOVEOFF", "SYNCMOVEON", "SYNCMOVERESUME",
    "SYNCMOVESUSPEND", "SYNCMOVEUNDO", "SYNCTOSENSOR", "SYSTEMSTOPACTION", "TESTSIGNDEFINE", "TESTSIGNRESET",
    "TEXTTABINSTALL", "TPERASE", "TPREADDNUM", "TPREADFK", "TPREADNUM", "TPSHOW", "TPWRITE", "TRIGGC", "TRIGGCHECKIO",
    "TRIGGDATACOPY", "TRIGGDATARESET", "TRIGGEQUIP", "TRIGGINT", "TRIGGIO", "TRIGGJ", "TRIGGJIOS", "TRIGGL",
    "TRIGGLIOS", "TRIGGRAMPAO", "TRIGGSPEED", "TRIGGSTOPPROC", "TRYINT", "TUNERESET", "TUNESERVO", "UIMSGBOX",
    "UISHOW", "UNLOAD", "UNPACKRAWBYTES", "VELSET", "WAITAI", "WAITAO", "WAITDI", "WAITDO", "WAITGI", "WAITGO",
    "WAITLOAD", "WAITROB", "WAITSENSOR", "WAITSYNCTASK", "WAITTESTANDSET", "WAITTIME", "WAITUNTIL", "WAITWOBJ",
    "WARMSTART", "WORLDACCLIM", "WRITE", "WRITEANYBIN", "WRITEBIN", "WRITEBLOCK", "WRITECFGDATA", "WRITERAWBYTES",
    "WRITESTRBIN", "WRITEVAR", "WZBOXDEF", "WZCYLDEF", "WZDISABLE", "WZDOSET", "WZENABLE", "WZFREE", "WZHOMEJOINTDEF",
    "WZLIMJOINTDEF", "WZLIMSUP", "WZSPHDEF",
}) | NO_TP.keys()  # fmt: skip
# RAPID's own data (with the ERR_ error numbers): no module declares it, it is not missing from the backup.
RAPID_DATA = frozenset({"ERRNO", "INTNO", "ROB_ID", "PI"})


def no_tp_equivalent(stmt: n.Stmt, routines: Iterable[str], type_of, converted: Iterable[str] = (),
                     karel: bool = False) -> str | None:
    """'Write: files and serial channels: ...' when the statement calls an instruction or a function of RAPID
    TP has nothing for, or sets, declares or reads data of such a type; None otherwise. The backup's own routines of
    the same name are not RAPID's; `converted`: what CrossArm converts after all (--karel: Open, Write...);
    `karel`: converting with --karel (sockets say it does not convert them)."""
    skipped = frozenset(converted)
    names: list[str] = [stmt.name] if isinstance(stmt, n.ProcCall) else []
    names += [node.name for node in nodes(stmt) if isinstance(node, n.FuncCall)]
    for name in names:
        if name.upper() in NO_TP and name.upper() not in routines and name.upper() not in skipped:
            return f"{name}: {why_none(name.upper(), karel)}"
    typed = stmt.type_name if isinstance(stmt, n.DataDecl) else None
    if isinstance(stmt, n.Assign) and (root := path_of(stmt.target)):
        typed = type_of(root[0])
    if typed is not None and typed.upper() in NO_TP and typed.upper() not in skipped:
        return f"{typed} data: {why_none(typed.upper(), karel)}"
    for node in nodes(stmt):  # IF answer=resCancel: what a UIMessageBox or SocketGetStatus gave
        if isinstance(node, n.Name) and (typed := type_of(node.name)) is not None and typed.upper() in NO_TP \
                and typed.upper() not in skipped:  # fmt: skip
            return f"{node.name} ({typed} data): {why_none(typed.upper(), karel)}"
    return None


# What a routine of the backup is for when it uses one of these, itself or in a routine it calls: a call to it
# that does not convert stays TODO for that (MbWriteLog writes a file), not for the text it was given.
_PASSED_ON = frozenset(why for why in NO_TP_FAMILIES if why.startswith(("files", "sockets", "raw byte")))


def _called(stmt: n.Stmt) -> list[str]:
    names = [stmt.name] if isinstance(stmt, n.ProcCall) else []
    return names + [node.name for node in nodes(stmt) if isinstance(node, n.FuncCall)]


class RoutineUse:
    """The files, sockets and byte buffers the backup's routines use, themselves or through the ones they call."""

    def __init__(self, routines: Mapping[str, n.Routine], provided: Iterable[str] = (),
                 converted: Iterable[str] = (), karel: bool = False) -> None:
        self.routines = routines  # upper-case name -> PROC or FUNC of the backup
        # upper-case names of the routines the integrator provides as programs (external_routines): what they
        # do is theirs, a routine calling one does not use files or sockets through it
        self.provided = frozenset(provided)
        self.converted = frozenset(converted)  # RAPID's instructions CrossArm converts after all (--karel)
        self.karel = karel  # converting with --karel: sockets say it does not convert them
        self._found: dict[str, tuple[tuple[str, ...], str] | None] = {}
        self._raised: dict[str, set[str]] | None = None  # error -> the routines raising it

    def raised_there(self, error: str) -> bool:
        """Whether the backup raises its error `error` (`RAISE ERR_X;`, `ErrRaise "ERR_X",...`), and does so only in
        routines using files, sockets or byte buffers, themselves or through the ones they call."""
        if self._raised is None:
            self._raised = defaultdict(set)
            for key, routine in self.routines.items():
                stmts = list(walk_statements(routine.body))
                for handler in routine.handlers:
                    if handler.kind == "ERROR_HANDLER" and (inner := handler_body(handler)) is not None:
                        stmts += walk_statements(inner)
                for stmt in stmts:
                    if isinstance(stmt, n.Unsupported) and stmt.kind == "RAISE":
                        if found := re.match(r"\s*RAISE\s+(\w+)", stmt.raw, re.IGNORECASE):
                            self._raised[found[1].upper()].add(key)
                    elif (isinstance(stmt, n.ProcCall) and stmt.name.upper() == "ERRRAISE" and stmt.args
                          and isinstance(stmt.args[0].value, n.String)):  # fmt: skip
                        self._raised[stmt.args[0].value.value.upper()].add(key)
        sites = self._raised.get(error.upper())
        return bool(sites) and all(self._uses(key) is not None for key in sites)

    def of(self, stmt: n.Stmt) -> str | None:
        """'MbWriteLog calls Open: files and serial channels: ...' when the statement calls a routine of the backup
        using what TP has nothing for; 'A, through B, calls SocketSend: ...' when it is B that does; else None."""
        for name in _called(stmt):
            if (found := self._uses(name.upper())) is not None:
                through, what = found
                return f"{name}, through {', '.join(through)}, calls {what}" if through else f"{name} calls {what}"
        return None

    def inside(self, name: str) -> str | None:
        """'SocketSend: sockets: ...' when the routine `name` uses files, sockets or byte buffers itself;
        'Open, called through HTML_create: files ...' when a routine it calls does; else None."""
        if (found := self._uses(name.upper())) is None:
            return None
        through, what = found
        if not through:
            return what
        called, why = what.split(": ", 1)
        return f"{called}, called through {', '.join(through)}: {why}"

    def byte_buffer(self, call: n.ProcCall, caller: Iterable[n.Stmt]) -> str | None:
        """'mbapBytes, given to ArrayCombine, is a byte buffer also passed to MbReceiveBytes, which calls
        SocketReceive: sockets: ...' when the call gives a byte array parameter of the backup's routine data the
        caller (its statements) hands to what uses files, sockets or byte buffers too: a frame, not numbers."""
        routine = self.routines.get(call.name.upper())
        if routine is None or not (given := _byte_arrays_given(call, routine.params)):
            return None
        for stmt in walk_statements(caller):
            for node in nodes(stmt):
                if not isinstance(node, n.ProcCall | n.FuncCall) or node is call:
                    continue
                passed = {v.name.upper() for v in nodes(node.args) if isinstance(v, n.Name)}
                if not (shared := [name for name in given if name.upper() in passed]):
                    continue
                upper = node.name.upper()
                if upper not in self.routines and NO_TP.get(upper) in _PASSED_ON:
                    where = f"{node.name}: {why_none(upper, self.karel)}"
                elif (found := self._uses(upper)) is not None:
                    through, what = found
                    via = f", through {', '.join(through)}," if through else ""
                    where = f"{self.routines[upper].name}, which{via} calls {what}"
                else:
                    continue
                return f"{shared[0]}, given to {call.name}, is a byte buffer also passed to {where}"
        return None

    def _uses(self, key: str) -> tuple[tuple[str, ...], str] | None:
        """(the routines in between, 'Open: why') for the routine `key`; None if it uses none."""
        if key in self._found or key not in self.routines or key in self.provided:
            return self._found.get(key)
        self._found[key] = None  # a routine calling itself back adds nothing
        for stmt in walk_statements(self.routines[key].body):
            for name in _called(stmt):
                upper = name.upper()
                if upper not in self.routines and NO_TP.get(upper) in _PASSED_ON and upper not in self.converted:
                    self._found[key] = ((), f"{name}: {why_none(upper, self.karel)}")
                    return self._found[key]
                if (inner := self._uses(upper)) is not None:
                    self._found[key] = ((self.routines[upper].name, *inner[0]), inner[1])
                    return self._found[key]
        return None


def _byte_arrays_given(call: n.ProcCall, params: str) -> list[str]:
    """The data the call gives to the byte array parameters of a routine with these raw parameters, in order."""
    required: list[bool] = []  # whether each required parameter is a byte array, in order
    optional: set[str] = set()  # the optional ones that are
    for part in split_params(params):
        for alternative in part.lstrip("\\").split("|"):
            is_bytes = re.search(r"\bbyte\s+(\w+)\s*\{", alternative, re.IGNORECASE)
            if part.startswith("\\"):
                optional |= {is_bytes[1].upper()} if is_bytes else set()
            else:
                required.append(bool(is_bytes))
    positional = [a for a in call.args if a.name is None]
    found = [a.value for a, is_bytes in zip(positional, required, strict=False) if is_bytes]
    found += [a.value for a in call.args if a.name is not None and a.name.upper() in optional]
    return [v.name for v in found if isinstance(v, n.Name)]


def _errno(expr: object) -> bool:
    return isinstance(expr, n.Name) and expr.name.upper() == "ERRNO"


def tested_errors(stmts: Iterable[n.Stmt]) -> set[str]:
    """The error numbers an ERROR handler compares ERRNO with: `IF ERRNO=ERR_X`, `TEST ERRNO CASE ERR_X:`."""
    found: set[str] = set()
    for stmt in walk_statements(stmts):
        if isinstance(stmt, n.Test) and _errno(stmt.subject):
            found |= {v.name.upper() for case in stmt.cases for v in case.values if isinstance(v, n.Name)}
        for node in nodes(stmt):
            if isinstance(node, n.BinaryOp) and node.op in ("=", "<>"):
                for side, other in ((node.left, node.right), (node.right, node.left)):
                    if _errno(side) and isinstance(other, n.Name):
                        found.add(other.name.upper())
    return found


def handles_files_or_sockets(stmts: Iterable[n.Stmt], type_of, use: RoutineUse) -> bool:
    """Whether an ERROR handler tests ERRNO against no error but those of files and sockets, and the backup's own
    (errnum data) raised only where files or sockets are used: in a routine using files or sockets, the errors it
    handles come from them."""
    return all(e in FILE_SOCKET_ERRORS or e.startswith("ERR_SOCK_") or (type_of(e) == "errnum" and use.raised_there(e))
               for e in tested_errors(stmts))  # fmt: skip


# RAPID text functions TP does otherwise, measured (ROBOGUIDE string probe, RobotStudio): a statement using one
# stays TODO with why, rather than as a value CrossArm could not work out.
TEXT_TODO = {
    "STRTOVAL": "StrToVal: TP reads a text as a number (R[n]=SR[m]) but gives 0 for one that is not a number and"
                " its first digits for '12AB', where RAPID returns FALSE and leaves the number as it was",
    "STRFIND": "StrFind: it looks for a character of a set; FINDSTR looks for a whole text (StrMatch)",
    "STRMEMB": "StrMemb: TP has no test of a character against a set",
    "STRORDER": "StrOrder: TP compares texts for equality only",
    "STRMAP": "StrMap: TP has no character mapping",
}  # fmt: skip


def text_todo(stmt: n.Stmt, routines: Iterable[str]) -> str | None:
    """Why a statement using a RAPID text function TP does otherwise stays TODO; None for any other."""
    for node in nodes(stmt):
        if isinstance(node, n.FuncCall) and node.name.upper() in TEXT_TODO and node.name.upper() not in routines:
            return TEXT_TODO[node.name.upper()]
    return None
