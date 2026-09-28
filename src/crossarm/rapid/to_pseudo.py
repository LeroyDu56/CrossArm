# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""AST -> human-readable pseudo-code listing.

Each line is prefixed with the source line it comes from, so the listing can
be read side by side with the original program. V1 instructions get a
normalised, role-labelled form (MOVE L to=... speed=...); unsupported
constructs are flagged with '??'.
"""

from crossarm.rapid import nodes as n

_INDENT = "  "

# Higher binds tighter; used to print only the parentheses that matter.
_PRECEDENCE = {
    "OR": 1, "XOR": 1,
    "AND": 2,
    "=": 4, "<>": 4, "<": 4, "<=": 4, ">": 4, ">=": 4,
    "+": 5, "-": 5,
    "*": 6, "/": 6, "DIV": 6, "MOD": 6,
}  # fmt: skip
_NOT_PRECEDENCE = 3
_UNARY_PRECEDENCE = 7


def format_expr(expr: n.Expr | None, parent_precedence: int = 0) -> str:
    match expr:
        case None:
            return ""
        case n.Number(text=text):
            return text
        case n.String(value=value):
            return '"' + value.replace("\\", "\\\\").replace('"', '""') + '"'
        case n.Bool(value=value):
            return "TRUE" if value else "FALSE"
        case n.Name(name=name):
            return name
        case n.Aggregate(items=items):
            return "[" + ", ".join(format_expr(i) for i in items) + "]"
        case n.Component(base=base, field=field):
            return f"{format_expr(base, 99)}.{field}"
        case n.Index(base=base, indices=indices):
            return f"{format_expr(base, 99)}{{{', '.join(format_expr(i) for i in indices)}}}"
        case n.FuncCall(name=name, args=args):
            return f"{name}({format_args(args)})"
        case n.UnaryOp(op="NOT", operand=operand):
            text = "NOT " + format_expr(operand, _NOT_PRECEDENCE)
            return f"({text})" if parent_precedence > _NOT_PRECEDENCE else text
        case n.UnaryOp(op=op, operand=operand):
            return op + format_expr(operand, _UNARY_PRECEDENCE)
        case n.BinaryOp(op=op, left=left, right=right):
            prec = _PRECEDENCE[op]
            # Right operand gets prec+1: RAPID operators are left-associative.
            text = f"{format_expr(left, prec)} {op} {format_expr(right, prec + 1)}"
            return f"({text})" if parent_precedence > prec else text
    raise TypeError(f"not an expression: {expr!r}")


def format_arg(arg: n.Arg) -> str:
    if arg.name is None:
        return format_expr(arg.value)
    if arg.value is None:
        return f"\\{arg.name}"
    separator = "?" if arg.conditional else ":="
    return f"\\{arg.name}{separator}{format_expr(arg.value)}"


def format_args(args: tuple[n.Arg, ...]) -> str:
    return ", ".join(format_arg(a) for a in args)


class _Printer:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def emit(self, line: int | None, depth: int, text: str) -> None:
        gutter = f"{line:5d} | " if line is not None else "      | "
        self.lines.append(gutter + _INDENT * depth + text)

    def module(self, module: n.Module) -> None:
        attrs = f" ({', '.join(module.attributes)})" if module.attributes else ""
        self.emit(module.span.line, 0, f"MODULE {module.name}{attrs}")
        for item in module.body:
            if isinstance(item, n.Routine):
                self.routine(item, 1)
            else:
                self.stmt(item, 1)
        self.emit(None, 0, "ENDMODULE")

    def routine(self, routine: n.Routine, depth: int) -> None:
        scope = f"{routine.scope} " if routine.scope else ""
        returns = f"{routine.return_type} " if routine.return_type else ""
        params = "" if routine.kind == "TRAP" else f"({routine.params})"
        self.emit(routine.span.line, depth, f"{scope}{routine.kind} {returns}{routine.name}{params}")
        self.body(routine.body, depth + 1)
        for handler in routine.handlers:
            self.stmt(handler, depth + 1)
        self.emit(None, depth, f"END{routine.kind}")

    def body(self, stmts: tuple[n.Stmt, ...], depth: int) -> None:
        for stmt in stmts:
            self.stmt(stmt, depth)

    def stmt(self, stmt: n.Stmt, depth: int) -> None:
        line = stmt.span.line
        match stmt:
            case n.Comment(text=text):
                self.emit(line, depth, f"!{text}")
            case n.DataDecl():
                scope = f"{stmt.scope} " if stmt.scope else ""
                dims = f"{{{', '.join(format_expr(d) for d in stmt.dims)}}}" if stmt.dims else ""
                init = f" := {format_expr(stmt.init)}" if stmt.init is not None else ""
                self.emit(line, depth, f"{scope}{stmt.storage} {stmt.type_name} {stmt.name}{dims}{init}")
            case n.Move():
                parts = [f"MOVE {stmt.kind.value:<4}"]
                if stmt.via_point is not None:
                    parts.append(f"via={format_expr(stmt.via_point)}")
                parts += [
                    f"to={format_expr(stmt.to_point)}",
                    f"speed={format_expr(stmt.speed)}",
                    f"zone={format_expr(stmt.zone)}",
                    f"tool={format_expr(stmt.tool)}",
                ]
                if stmt.wobj is not None:
                    parts.append(f"wobj={format_expr(stmt.wobj)}")
                parts += [format_arg(a) for a in stmt.options]
                self.emit(line, depth, "  ".join(parts))
            case n.SetSignal(signal=signal, value=value):
                self.emit(line, depth, f"SET       {format_expr(signal)} = {value}")
            case n.WaitTime(seconds=seconds, options=options):
                extra = "  " + "  ".join(format_arg(a) for a in options) if options else ""
                self.emit(line, depth, f"WAIT      {format_expr(seconds)} s{extra}")
            case n.ProcCall(name=name, args=args):
                self.emit(line, depth, f"CALL      {name}" + (f"  {format_args(args)}" if args else ""))
            case n.Assign(target=target, value=value):
                self.emit(line, depth, f"{format_expr(target)} := {format_expr(value)}")
            case n.If():
                self.if_stmt(stmt, depth)
            case n.For():
                step = f" STEP {format_expr(stmt.step)}" if stmt.step is not None else ""
                header = f"FOR {stmt.var} FROM {format_expr(stmt.start)} TO {format_expr(stmt.end)}{step} DO"
                self.emit(line, depth, header)
                self.body(stmt.body, depth + 1)
                self.emit(None, depth, "ENDFOR")
            case n.While(condition=condition, body=body):
                self.emit(line, depth, f"WHILE {format_expr(condition)} DO")
                self.body(body, depth + 1)
                self.emit(None, depth, "ENDWHILE")
            case n.Test():
                self.emit(line, depth, f"TEST {format_expr(stmt.subject)}")
                for case in stmt.cases:
                    self.emit(None, depth, f"CASE {', '.join(format_expr(v) for v in case.values)}:")
                    self.body(case.body, depth + 1)
                if stmt.default is not None:
                    self.emit(None, depth, "DEFAULT:")
                    self.body(stmt.default, depth + 1)
                self.emit(None, depth, "ENDTEST")
            case n.Return(value=value):
                self.emit(line, depth, f"RETURN {format_expr(value)}".rstrip())
            case n.Exit():
                self.emit(line, depth, "EXIT")
            case n.Unsupported(kind=kind, raw=raw):
                raw_lines = raw.splitlines() or [""]
                more = f"  (+{len(raw_lines) - 1} lines)" if len(raw_lines) > 1 else ""
                self.emit(line, depth, f"?? [{kind}] {raw_lines[0].strip()}{more}")
            case _:
                raise TypeError(f"unknown statement: {stmt!r}")

    def if_stmt(self, stmt: n.If, depth: int) -> None:
        if stmt.compact:
            branch = stmt.branches[0]
            self.emit(stmt.span.line, depth, f"IF {format_expr(branch.condition)} THEN  (one-line IF)")
            self.body(branch.body, depth + 1)
            self.emit(None, depth, "ENDIF")
            return
        for i, branch in enumerate(stmt.branches):
            keyword = "IF" if i == 0 else "ELSEIF"
            self.emit(stmt.span.line if i == 0 else None, depth, f"{keyword} {format_expr(branch.condition)} THEN")
            self.body(branch.body, depth + 1)
        if stmt.else_body:
            self.emit(None, depth, "ELSE")
            self.body(stmt.else_body, depth + 1)
        self.emit(None, depth, "ENDIF")


def to_pseudo(module: n.Module) -> str:
    printer = _Printer()
    printer.module(module)
    return "\n".join(printer.lines) + "\n"
