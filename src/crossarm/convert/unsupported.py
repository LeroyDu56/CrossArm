# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What TP has nothing for, or does otherwise: RAPID instructions, functions and data types a statement
using one stays TODO for, with why, as does a call to a routine of the backup using files or sockets; and RAPID's
own instructions and data, which a backup never declares."""

from collections.abc import Iterable, Mapping

from crossarm.convert.compute import path_of
from crossarm.convert.records import nodes
from crossarm.rapid import nodes as n
from crossarm.rapid.walk import walk_statements

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
    "ABB system instruction (program modules, system data, mechanical units): TP has none": (
        "GETSYSDATA", "SETSYSDATA", "SAVE", "LOAD", "UNLOAD", "STARTLOAD", "WAITLOAD", "ERASEMODULE",
        "ACTUNIT", "DEACTUNIT",
    ),
    "world zone: the FANUC sets zones up in its DCS or interference check menus, not in TP": (
        "WZBOXDEF", "WZCYLDEF", "WZSPHDEF", "WZHOMEJOINTDEF", "WZLIMJOINTDEF", "WZLIMSUP", "WZDOSET",
        "WZENABLE", "WZDISABLE", "WZFREE", "WZSTATIONARY", "WZTEMPORARY", "SHAPEDATA",
    ),
}  # fmt: skip
NO_TP = {name: why for why, names in NO_TP_FAMILIES.items() for name in names}

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


def no_tp_equivalent(stmt: n.Stmt, routines: Iterable[str], type_of) -> str | None:
    """'Write: files and serial channels: ...' when the statement calls an instruction or a function of RAPID
    TP has nothing for, or sets, declares or reads data of such a type; None otherwise. The backup's own routines of
    the same name are not RAPID's."""
    names: list[str] = [stmt.name] if isinstance(stmt, n.ProcCall) else []
    names += [node.name for node in nodes(stmt) if isinstance(node, n.FuncCall)]
    for name in names:
        if name.upper() in NO_TP and name.upper() not in routines:
            return f"{name}: {NO_TP[name.upper()]}"
    typed = stmt.type_name if isinstance(stmt, n.DataDecl) else None
    if isinstance(stmt, n.Assign) and (root := path_of(stmt.target)):
        typed = type_of(root[0])
    if typed is not None and typed.upper() in NO_TP:
        return f"{typed} data: {NO_TP[typed.upper()]}"
    for node in nodes(stmt):  # IF answer=resCancel: what a UIMessageBox or SocketGetStatus gave
        if isinstance(node, n.Name) and (typed := type_of(node.name)) is not None and typed.upper() in NO_TP:
            return f"{node.name} ({typed} data): {NO_TP[typed.upper()]}"
    return None


# What a routine of the backup is for when it uses one of these, itself or in a routine it calls: a call to it
# that does not convert stays TODO for that (MbWriteLog writes a file), not for the text it was given.
_PASSED_ON = frozenset(why for why in NO_TP_FAMILIES if why.startswith(("files", "sockets", "raw byte")))


def _called(stmt: n.Stmt) -> list[str]:
    names = [stmt.name] if isinstance(stmt, n.ProcCall) else []
    return names + [node.name for node in nodes(stmt) if isinstance(node, n.FuncCall)]


class RoutineUse:
    """The files, sockets and byte buffers the backup's routines use, themselves or through the ones they call."""

    def __init__(self, routines: Mapping[str, n.Routine]) -> None:
        self.routines = routines  # upper-case name -> PROC or FUNC of the backup
        self._found: dict[str, tuple[tuple[str, ...], str] | None] = {}

    def of(self, stmt: n.Stmt) -> str | None:
        """'MbWriteLog calls Open: files and serial channels: ...' when the statement calls a routine of the backup
        using what TP has nothing for; 'A, through B, calls SocketSend: ...' when it is B that does; else None."""
        for name in _called(stmt):
            if (found := self._uses(name.upper())) is not None:
                through, what = found
                return f"{name}, through {', '.join(through)}, calls {what}" if through else f"{name} calls {what}"
        return None

    def _uses(self, key: str) -> tuple[tuple[str, ...], str] | None:
        """(the routines in between, 'Open: why') for the routine `key`; None if it uses none."""
        if key in self._found or key not in self.routines:
            return self._found.get(key)
        self._found[key] = None  # a routine calling itself back adds nothing
        for stmt in walk_statements(self.routines[key].body):
            for name in _called(stmt):
                upper = name.upper()
                if upper not in self.routines and NO_TP.get(upper) in _PASSED_ON:
                    self._found[key] = ((), f"{name}: {NO_TP[upper]}")
                    return self._found[key]
                if (inner := self._uses(upper)) is not None:
                    self._found[key] = ((self.routines[upper].name, *inner[0]), inner[1])
                    return self._found[key]
        return None


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
