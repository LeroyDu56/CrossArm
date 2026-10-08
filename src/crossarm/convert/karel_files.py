# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID's text files written by KAREL (--karel): Open, Write and Close as calls to CA_FILE (crossarm.karel).

    VAR iodev logF;                                       R[n:logF] keeps the file's handle (0: none open)
    Open "HOME:" \\File:="log.txt", logF \\Append;          CALL CA_FILE(1,n,2,'UD1:','log.txt')
    Write logF, "count " + sName \\Num:=nCount;            CALL CA_FILE(2,n,1,'count ',SR[3],R[5:nCount])
    Write logF, "x" \\NoNewLine;                           CALL CA_FILE(2,n,0,'x')
    Close logF;                                          CALL CA_FILE(3,n)

The handle argument is the NUMBER of the register keeping it (an element of an iodev array: its register, or
R[i] holding that number when the index is only known at run time). The file name and the text are given in
parts: texts known now as TP texts (38 characters at most each, an apostrophe written as a backquote that
CA_FILE turns back into one), texts kept in string registers as SR[n] (AR[n] for a text parameter), any other
text worked out first into a scratch string register; \\Num a number, a constant or R[i]. A CALL takes 10
arguments: a longer Write is written in several, all but the last with no new line.

A file of RAPID's HOME: is written on the controller's UD1: (the USB memory stick, an MS-DOS file system read
on a PC as HOME: is): FR: is the F-ROM, where KAREL must not rewrite nor append to a file; RD: is lost at power
off; MD: holds the programs. Measured on ROBOGUIDE V10.10 (tools/make_karel_file_probe.py): the bytes written
are RAPID's (lines ended by CR LF, numbers with six significant digits, \\Append adding to the end, a file
emptied when opened again with \\Write); writing to a handle with no file open stops the program on the CALL
(INTP-328 File is not opened), as does a device the controller does not have (FILE-008) or a folder of HOME:
given at run time (INTP-325 Invalid file string). A file stays open from one CALL to the next while the program
runs; the controller closes it, keeping what was written, when the TP program ends or aborts (RAPID keeps it
open until the program is started again). RAPID's numbers: its Write \\Num rule (six significant digits, a
whole number when the decimals are within 0.000005 of one); RobotStudio was not used to compare them.
"""

from typing import TYPE_CHECKING

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.strings import TEXT_PIECE
from crossarm.convert.tp_numbers import decimal
from crossarm.karel import PROGRAMS
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

if TYPE_CHECKING:
    from crossarm.convert.translate import Converter

PROGRAM = "CA_FILE"
DEVICE = "UD1:"  # where the files of HOME: are written (module docstring)
OPEN, WRITE, CLOSE = 1, 2, 3  # CA_FILE's first argument
WRITE_MODE, APPEND_MODE = 1, 2
INSTRUCTIONS = frozenset({"OPEN", "WRITE", "CLOSE"})
CONVERTED = INSTRUCTIONS | {"IODEV"}  # what --karel converts of RAPID's files: unsupported.NO_TP leaves them out
MAX_ARGUMENTS = 10  # a TP CALL (measured: 10 run)
SCRATCH_TEXTS = 3  # scratch string registers one CALL takes its worked-out texts from
HOME = "HOME:"
PREDEFINED_DIRECTORIES = {"DISKHOME": HOME}  # RAPID's own: the backup never declares them
WHY = "files and serial channels"


def file_call(c: "Converter", arguments: list[str]) -> str:
    if len(PROGRAM) > c.config.program_name_max_length:
        raise Untranslatable(f"KAREL program {PROGRAM}: longer than the {c.config.program_name_max_length} characters"
                             " a program name has on this controller", Blocker.NO_TP_EQUIVALENT)  # fmt: skip
    assert PROGRAM in PROGRAMS
    return f"CALL {PROGRAM}({','.join(arguments)})"


def _bare(register: str) -> str:
    """R[5:nCount] as a CALL argument takes it: R[5]."""
    return register.split(":", 1)[0] + "]" if ":" in register else register


class KarelFiles:
    """The routine translator's part that writes RAPID's files through CA_FILE (mixed into it)."""

    def file_statement(self, call: n.ProcCall, name: str) -> None:
        positional = [a.value for a in call.args if a.name is None]
        options = {(a.name or "").upper(): a.value for a in call.args if a.name is not None}
        if None in positional or not positional:
            raise Untranslatable(f"{call.name}: {WHY}: an argument is missing", Blocker.NO_TP_EQUIVALENT)
        if name == "CLOSE":
            if len(positional) != 1 or options:
                raise Untranslatable(f"Close with these arguments: {WHY}", Blocker.NO_TP_EQUIVALENT)
            self.emit(file_call(self.c, [str(CLOSE), self.file_handle(positional[0])]))  # type: ignore[attr-defined]
        elif name == "OPEN":
            self.file_open(positional, options)
        else:
            self.file_write(positional, options)
        self.c.warn_once(  # type: ignore[attr-defined]
            "karel:files", self.name, call.span.line,  # type: ignore[attr-defined]
            f"files of RAPID's HOME: are written on the controller's {DEVICE} (its USB memory stick, read on a PC as"
            f" HOME: is) by CrossArm's KAREL program {PROGRAM}: plug a stick in before the programs run", Blocker.OTHER,
        )  # fmt: skip

    def file_handle(self, expr: n.Expr) -> str:
        """The CALL argument naming the register that keeps an iodev: its number, or R[i] holding it."""
        if isinstance(expr, n.Name):
            decl = self.c.symbols.get(expr.name)  # type: ignore[attr-defined]
            if decl is not None and decl.type_name.lower() == "iodev" and not decl.dims \
                    and not (self.args and self.args.kind(expr.name)):  # type: ignore[attr-defined]  # fmt: skip
                register = self.c.written_register(decl.name)  # type: ignore[attr-defined]
                return register[2 : register.index(":")] if ":" in register else register[2:-1]
        if isinstance(expr, n.Index) and isinstance(expr.base, n.Name):
            decl = self.c.symbols.get(expr.base.name)  # type: ignore[attr-defined]
            if decl is not None and decl.type_name.lower() == "iodev":
                element = self.array_element(expr, True, "iodev")  # type: ignore[attr-defined]
                if element is not None:
                    return element[2:-1]  # {RB:...}, its number once the block is placed; or R[i] holding it
        raise Untranslatable(f"'{format_expr(expr)}': {WHY}: CrossArm keeps the handle of an iodev data of the backup"
                             " or an element of an array of them", Blocker.NO_TP_EQUIVALENT)  # fmt: skip

    def file_open(self, positional: list, options: dict) -> None:
        if len(positional) != 2:
            raise Untranslatable(f"Open with these arguments: {WHY}", Blocker.NO_TP_EQUIVALENT)
        switches = set(options) - {"FILE"}
        if not switches <= {"WRITE", "APPEND"} or len(switches) > 1 or any(options[s] is not None for s in switches):
            names = ", ".join(f"\\{s.title()}" for s in sorted(switches - {"WRITE", "APPEND"})) or "both switches"
            raise Untranslatable(f"Open {names}: {WHY}: CrossArm writes text files opened with \\Write or \\Append",
                                 Blocker.NO_TP_EQUIVALENT)  # fmt: skip
        directory = self.file_directory(positional[0])
        handle = self.file_handle(positional[1])
        name: list[n.Expr] = []
        if directory and "FILE" in options:
            raise Untranslatable(f"Open {format_expr(positional[0])}: {WHY}: a folder of {HOME} (CrossArm writes the"
                                 f" files of {HOME} itself)", Blocker.NO_TP_EQUIVALENT)  # fmt: skip
        if directory:
            name.append(n.String(positional[0].span, directory))
        if "FILE" in options:
            if options["FILE"] is None:
                raise Untranslatable(f"Open \\File without a name: {WHY}", Blocker.NO_TP_EQUIVALENT)
            name.append(options["FILE"])
        if not name:
            raise Untranslatable(f"Open of {HOME} without a file name: {WHY}", Blocker.NO_TP_EQUIVALENT)
        mode = APPEND_MODE if "APPEND" in switches else WRITE_MODE
        folder = n.String(positional[0].span, DEVICE) if directory is not None else positional[0]
        parts = self.file_parts([folder, *name], name_only=True)
        self.file_calls([str(OPEN), handle, str(mode)], parts, None)

    def file_directory(self, expr: n.Expr) -> str | None:
        """What follows HOME: in Open's first argument ('' for HOME: itself); None for a text only known at run
        time (a string parameter: CA_FILE writes HOME: on UD1: and stops on a folder of it, any other device is
        the controller's); a TODO for any other device."""
        text = self.fixed_text(expr)  # type: ignore[attr-defined]
        if text is None and isinstance(expr, n.Name) and self.c.symbols.get(expr.name) is None \
                and not (self.args and self.args.kind(expr.name)):  # type: ignore[attr-defined]  # fmt: skip
            text = PREDEFINED_DIRECTORIES.get(expr.name.upper())
            if text is None:
                raise Untranslatable(f"Open {format_expr(expr)}: {WHY}: CrossArm writes the files of {HOME}",
                                     Blocker.NO_TP_EQUIVALENT)  # fmt: skip
        if text is None:
            return None
        if not text.upper().startswith(HOME):
            raise Untranslatable(f"Open \"{text}\": {WHY}: CrossArm writes the files of {HOME} only",
                                 Blocker.NO_TP_EQUIVALENT)  # fmt: skip
        rest = text[len(HOME) :].lstrip("/\\")
        if "/" in rest or "\\" in rest:
            raise Untranslatable(f"Open \"{text}\": {WHY}: a folder of {HOME} (CrossArm writes the files of"
                                 f" {HOME} itself)", Blocker.NO_TP_EQUIVALENT)  # fmt: skip
        return rest

    def file_write(self, positional: list, options: dict) -> None:
        if len(positional) != 2:
            raise Untranslatable(f"Write with these arguments: {WHY}", Blocker.NO_TP_EQUIVALENT)
        others = set(options) - {"NUM", "NONEWLINE"}
        if others:
            names = ", ".join(f"\\{s.title()}" for s in sorted(others))
            raise Untranslatable(f"Write {names}: {WHY}: CrossArm writes texts and \\Num", Blocker.NO_TP_EQUIVALENT)
        if "NONEWLINE" in options and options["NONEWLINE"] is not None:
            raise Untranslatable(f"Write \\NoNewLine with a value: {WHY}", Blocker.NO_TP_EQUIVALENT)
        handle = self.file_handle(positional[0])
        parts = self.file_parts([positional[1]])
        number = options.get("NUM")
        if "NUM" in options:
            if number is None:
                raise Untranslatable(f"Write \\Num without a value: {WHY}", Blocker.NO_TP_EQUIVALENT)
            parts.append(("num", number))
        self.file_calls([str(WRITE), handle], parts, "NONEWLINE" not in options)

    def file_parts(self, texts: list[n.Expr], name_only: bool = False) -> list:
        """The text pieces: a str for a text known now (one CALL argument each), an expression otherwise."""
        parts: list = []
        for text in texts:
            for part in self._text_parts(text):  # type: ignore[attr-defined]
                fixed = self.fixed_text(part)  # type: ignore[attr-defined]
                if fixed is None:
                    parts.append(part)
                    continue
                if not fixed.isascii() or any(ord(ch) < 32 for ch in fixed) or "`" in fixed:
                    raise Untranslatable(f"text '{format_expr(part)}': {WHY}: it has a character a TP text does not"
                                         " pass", Blocker.NO_TP_EQUIVALENT)  # fmt: skip
                if name_only and ("/" in fixed or "\\" in fixed):
                    raise Untranslatable(f"file name '{fixed}': {WHY}: a folder of {HOME} (CrossArm writes the files"
                                         f" of {HOME} itself)", Blocker.NO_TP_EQUIVALENT)  # fmt: skip
                fixed = fixed.replace("'", "`")  # CA_FILE turns it back into an apostrophe
                if parts and isinstance(parts[-1], str) and len(parts[-1]) + len(fixed) <= TEXT_PIECE:
                    parts[-1] += fixed
                    continue
                parts += [fixed[i : i + TEXT_PIECE] for i in range(0, len(fixed), TEXT_PIECE)] or [""]
        return parts

    def file_calls(self, head: list[str], parts: list, new_line: bool | None) -> None:
        """CALL CA_FILE(head..., [new line,] parts...): several when the parts take more arguments than a CALL
        has, or more worked-out texts than the scratch string registers; only the last one ends the line."""
        if not parts:
            parts = [""]
        room = MAX_ARGUMENTS - len(head) - (new_line is not None)
        pending: list[str] = []
        scratch = 0
        for i, part in enumerate(parts):
            if isinstance(part, str):
                argument = f"'{part}'"
            elif isinstance(part, tuple):
                argument = decimal(self.single(part[1], 1))  # type: ignore[attr-defined]
                argument = _bare(argument) if argument.startswith("R[") else argument
            elif (register := self.file_text_register(part)) is not None:
                argument = register
            else:
                if scratch == SCRATCH_TEXTS:
                    if new_line is None:
                        raise Untranslatable(f"a file name of more than {SCRATCH_TEXTS} texts worked out: {WHY}",
                                             Blocker.NO_TP_EQUIVALENT)  # fmt: skip
                    self.emit(file_call(self.c, [*head, "0", *pending]))  # type: ignore[attr-defined]
                    pending, scratch = [], 0
                scratch += 1
                register = self.text_scratch(scratch)  # type: ignore[attr-defined]
                self.load_text(part, register, tuple(s for s in range(scratch + 1, scratch + 3)))  # type: ignore[attr-defined]
                argument = register
            pending.append(argument)
            if len(pending) == room and i < len(parts) - 1:
                if new_line is None:
                    raise Untranslatable(f"a file name in more than {room} parts: {WHY}", Blocker.NO_TP_EQUIVALENT)
                self.emit(file_call(self.c, [*head, "0", *pending]))  # type: ignore[attr-defined]
                pending, scratch = [], 0
        flag = [] if new_line is None else [str(int(new_line))]
        self.emit(file_call(self.c, [*head, *flag, *pending]))  # type: ignore[attr-defined]

    def file_text_register(self, expr: n.Expr) -> str | None:
        """SR[n] or AR[n] holding a text as it is (a CALL argument passes a copy of it)."""
        try:
            return self.text_register(expr)  # type: ignore[attr-defined]
        except Untranslatable:
            return None
