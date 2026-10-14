# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Load, StartLoad, WaitLoad, UnLoad and EraseModule: program modules loaded and unloaded at run time (a mixin of
the routine translator).

A large cell often keeps the programs of each product or station in a module of its own, loaded when it is needed:

    Load \\Dynamic, "HOME:/PartA.mod";        !l.12 Load PartA (loaded)
    StartLoad \\Dynamic, diskhome \\File:="PartA.mod", load1;   (likewise)   WaitLoad load1;   (likewise)
    UnLoad "HOME:/PartA.mod";                 !l.20 UnLoad PartA (kept)

A FANUC controller has no modules: every program CrossArm writes is loaded on it, side by side. A module the backup
holds is converted with the others, so its programs are there before the line runs; the line is a remark, with a
warning saying so (the programs are not removed at UnLoad: two modules declaring the same routine, loaded one at a
time on the ABB, cannot both be on the FANUC under one name). A module the backup does not hold is TODO: its
programs are to be loaded on the controller; so is one whose file is named at run time. Both are TODO under
Blocker.LOADED_MODULE, and kept (ConversionResult.loaded_missing, with the file's path as the RAPID names it) for the
analysis: add these files to the input and convert again. Save stays TODO (TP writes no file:
crossarm.convert.unsupported).
"""

from dataclasses import dataclass

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.compute import Typed
from crossarm.convert.late_calls import _pattern
from crossarm.convert.tp_numbers import ascii_text
from crossarm.convert.values import Unresolvable
from crossarm.rapid import nodes as n
from crossarm.rapid.walk import walk_statements

INSTRUCTIONS = frozenset({"LOAD", "STARTLOAD", "WAITLOAD", "UNLOAD", "ERASEMODULE"})
_EXTENSIONS = (".MODX", ".MOD", ".SYSX", ".SYS", ".PRG")


@dataclass(frozen=True, slots=True)
class MissingModule:
    """A module a Load / StartLoad / WaitLoad / UnLoad names that the input does not hold."""

    module: str  # upper case, '' when the file is named at run time
    path: str  # as the RAPID names it ('HOME:/hinge/HingeJobs2.mod'), '' when named at run time
    program: str  # the TP program and RAPID line left TODO for it
    line: int


def module_of(path: str) -> str:
    """'HOME:/Parts/PartA.modx' -> 'PARTA': the module a file holds, as RAPID names it after its file."""
    name = path.replace("\\", "/").rsplit("/", 1)[-1].rsplit(":", 1)[-1].strip()
    upper = name.upper()
    for extension in _EXTENSIONS:
        if upper.endswith(extension):
            return upper[: -len(extension)]
    return upper


class ModuleLoads:
    """The routine translator's part that writes module loads (mixed into it): needs c, emit(), rapid_text(),
    _constant_text() (convert.late_calls)."""

    def module_load(self, call: n.ProcCall, name: str) -> None:
        """Load / StartLoad / UnLoad / EraseModule / WaitLoad: a remark when the module is in the backup."""
        if name == "WAITLOAD":
            found = self._waited_modules(call)
        else:
            found = [self._loaded_module(call, name)]
        modules = [module for module, _ in found]
        held = {m.name.upper(): m.name for m in self.c.modules}  # type: ignore[attr-defined]
        absent = [(m, path) for m, path in found if m not in held]
        if absent:
            missing = self.c.result.loaded_missing  # type: ignore[attr-defined]
            missing += [MissingModule(m, path, self.name, call.span.line) for m, path in absent]  # type: ignore[attr-defined]
            raise Untranslatable(f"{call.name}: module {', '.join(m for m, _ in absent)} is not in the input: add its"
                                 " file to the backup and convert again, or load its programs on the controller",
                                 Blocker.LOADED_MODULE)  # fmt: skip
        names = ", ".join(held[m] for m in modules)
        from crossarm.convert.translate import REMARK_MAX

        what = "kept" if name in ("UNLOAD", "ERASEMODULE") else "loaded"
        text = ascii_text(f"l.{call.span.line} {call.name} {names}")
        self.emit(("!" + (text + f" ({what})" if len(text) + len(what) + 3 <= REMARK_MAX else text))[: REMARK_MAX + 1].rstrip())  # type: ignore[attr-defined]
        self.c.warn_once(f"module-load:{self.name}:{call.span.line}", self.name, call.span.line,  # type: ignore[attr-defined]
                         f"{call.name} {names}: a FANUC controller has no modules; the programs of {names}, converted"
                         " with the others, are loaded on it before the line runs, and stay there after an UnLoad:"
                         " nothing is loaded or unloaded at run time", Blocker.OTHER)  # fmt: skip

    def _loaded_module(self, call: n.ProcCall, name: str) -> tuple[str, str]:
        """(module, file path) a Load / StartLoad / UnLoad / EraseModule names: from its file path (and \\File);
        EraseModule names the module only ('' for its path)."""
        positional = [a.value for a in call.args if a.name is None and a.value is not None]
        named = {a.name.upper(): a.value for a in call.args if a.name is not None}
        if not positional:
            raise Untranslatable(f"{call.name}: no module named", Blocker.MISSING)
        path = self._module_text(call, positional[0])
        if name == "ERASEMODULE":
            return path.strip().upper(), ""
        if (file := named.get("FILE")) is not None:
            path = path.rstrip("/\\") + "/" + self._module_text(call, file)
        return module_of(path), path

    def _module_text(self, call: n.ProcCall, expr: n.Expr) -> str:
        found = _pattern(expr, self._text_now)
        if isinstance(found, str):
            return found
        self.c.result.loaded_missing.append(MissingModule("", "", self.name, call.span.line))  # type: ignore[attr-defined]
        raise Untranslatable(f"{call.name}: the module's file is named at run time: add every module it may load to"
                             " the input and convert again, or load their programs on the controller",
                             Blocker.LOADED_MODULE)  # fmt: skip

    def _text_now(self, expr: n.Expr) -> str | None:
        """A text known at conversion: a literal, a CONST, data no program changes."""
        text = self._constant_text(expr)  # type: ignore[attr-defined]
        if text is not None or not isinstance(expr, n.Name):
            return text
        try:
            value = self.c.computer.value(expr)  # type: ignore[attr-defined]
        except Unresolvable:
            return None
        return value.value if isinstance(value, Typed) and isinstance(value.value, str) else None

    def _waited_modules(self, call: n.ProcCall) -> list[tuple[str, str]]:
        """WaitLoad session: the modules every StartLoad of the task given that session loads (and \\UnloadPath)."""
        positional = [a.value for a in call.args if a.name is None and a.value is not None]
        if len(positional) != 1 or not isinstance(positional[0], n.Name):
            raise Untranslatable("WaitLoad: a load session named in the line is converted", Blocker.VALUE)
        session = positional[0].name.upper()
        modules: list[tuple[str, str]] = []
        for module in self.c.modules:  # type: ignore[attr-defined]
            for routine in module.routines:
                for stmt in walk_statements(routine.body):
                    if not isinstance(stmt, n.ProcCall) or stmt.name.upper() != "STARTLOAD":
                        continue
                    given = [a.value for a in stmt.args if a.name is None and a.value is not None]
                    if given and isinstance(given[-1], n.Name) and given[-1].name.upper() == session:
                        modules.append(self._loaded_module(stmt, "STARTLOAD"))
        if not modules:
            raise Untranslatable(f"WaitLoad {positional[0].name}: no StartLoad of the task starts this session",
                                 Blocker.MISSING)  # fmt: skip
        named = {a.name.upper(): a.value for a in call.args if a.name is not None}
        if (unload := named.get("UNLOADPATH")) is not None:
            path = self._module_text(call, unload)
            if (file := named.get("UNLOADFILE")) is not None:
                path = path.rstrip("/\\") + "/" + self._module_text(call, file)
            modules.append((module_of(path), path))
        return list(dict.fromkeys(modules))


__all__ = ["INSTRUCTIONS", "MissingModule", "ModuleLoads", "module_of"]
