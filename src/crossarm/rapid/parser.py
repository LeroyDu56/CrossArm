# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID recursive-descent parser: tokens -> nodes.Module.

One method per grammar rule (see docs/rapid_grammar_v1.ebnf).

Error handling strategy — industrial programs are much bigger than the V1 subset:
  * Constructs outside V1 that have a clear extent (RECORD...ENDRECORD, ERROR
    handlers, GOTO, late-binding calls...) are skipped on purpose and kept as
    nodes.Unsupported with their raw text.
  * A statement the parser cannot read is rewound, skipped as a whole (compound
    blocks are balanced) and also becomes an Unsupported node, plus an error
    diagnostic. Parsing then resumes with the next statement.
"""

from crossarm.diagnostics import Diagnostic, Severity, Span
from crossarm.rapid import nodes as n
from crossarm.rapid.lexer import tokenize
from crossarm.rapid.tokens import CommentToken, Token, TokenKind


class ParseError(Exception):
    def __init__(self, message: str, token: Token) -> None:
        super().__init__(message)
        self.message = message
        self.token = token


_BLOCK_OPENERS = {"IF": "ENDIF", "FOR": "ENDFOR", "WHILE": "ENDWHILE", "TEST": "ENDTEST"}
_BLOCK_CLOSERS = frozenset(_BLOCK_OPENERS.values())
_ROUTINE_ENDS = {"PROC": "ENDPROC", "FUNC": "ENDFUNC", "TRAP": "ENDTRAP"}
_HANDLER_KEYWORDS = frozenset({"ERROR", "UNDO", "BACKWARD"})
# Keywords that end the enclosing block: a statement never starts with one.
_BLOCK_BOUNDARIES = (
    _BLOCK_CLOSERS
    | frozenset(_ROUTINE_ENDS.values())
    | _HANDLER_KEYWORDS
    | {"ELSE", "ELSEIF", "CASE", "DEFAULT", "ENDMODULE", "ENDRECORD"}
)

_MOVES = {"MOVEJ": n.MoveKind.J, "MOVEL": n.MoveKind.L, "MOVEC": n.MoveKind.C, "MOVEABSJ": n.MoveKind.ABSJ}

_RELATIONAL = ("=", "<>", "<", "<=", ">", ">=")


def parse(text: str) -> tuple[n.Module | None, list[Diagnostic]]:
    """Parse a whole RAPID module. Never raises on bad input."""
    lexed = tokenize(text)
    parser = Parser(text, lexed.tokens, lexed.comments)
    module = parser.parse_module()
    return module, lexed.diagnostics + parser.diagnostics


class Parser:
    def __init__(self, text: str, tokens: list[Token], comments: list[CommentToken]) -> None:
        self.text = text
        self.tokens = tokens
        self.pos = 0
        self.comments = comments
        self.comment_pos = 0
        self.diagnostics: list[Diagnostic] = []

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    @property
    def tok(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset: int = 1) -> Token:
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def advance(self) -> Token:
        token = self.tok
        if token.kind is not TokenKind.EOF:
            self.pos += 1
        return token

    def accept_op(self, op: str) -> bool:
        if self.tok.is_op(op):
            self.advance()
            return True
        return False

    def accept_kw(self, word: str) -> bool:
        if self.tok.is_kw(word):
            self.advance()
            return True
        return False

    def expect_op(self, op: str) -> Token:
        if not self.tok.is_op(op):
            raise ParseError(f"expected '{op}', found {self.tok.describe()}", self.tok)
        return self.advance()

    def expect_kw(self, word: str) -> Token:
        if not self.tok.is_kw(word):
            raise ParseError(f"expected {word}, found {self.tok.describe()}", self.tok)
        return self.advance()

    def expect_ident(self) -> Token:
        if self.tok.kind is not TokenKind.IDENT:
            raise ParseError(f"expected a name, found {self.tok.describe()}", self.tok)
        return self.advance()

    @staticmethod
    def span(token: Token) -> Span:
        return Span(token.line, token.col)

    def raw_since(self, start: Token) -> str:
        """Exact source text from `start` up to the last consumed token."""
        end = self.tokens[self.pos - 1].end if self.pos > 0 else start.end
        return self.text[start.start : max(end, start.end)]

    def error(self, message: str, token: Token) -> None:
        self.diagnostics.append(Diagnostic(Severity.ERROR, message, self.span(token)))

    # ------------------------------------------------------------------
    # Comments: kept aside by the lexer, re-inserted between statements
    # ------------------------------------------------------------------

    def take_comments_before(self, offset: int) -> list[n.Comment]:
        out = []
        while self.comment_pos < len(self.comments) and self.comments[self.comment_pos].start < offset:
            c = self.comments[self.comment_pos]
            out.append(n.Comment(Span(c.line, c.col), c.text))
            self.comment_pos += 1
        return out

    def drop_comments_before(self, offset: int) -> None:
        """Comments inside a skipped region already live in its raw text."""
        self.take_comments_before(offset)

    # ------------------------------------------------------------------
    # Module level
    # ------------------------------------------------------------------

    def parse_module(self) -> n.Module | None:
        leading: list[n.ModuleItem] = list(self.take_comments_before(self.tok.start))
        start = self.tok
        try:
            self.expect_kw("MODULE")
            name = self.expect_ident().text
            attributes: list[str] = []
            if self.accept_op("("):
                while not self.tok.is_op(")"):
                    if self.tok.kind not in (TokenKind.IDENT, TokenKind.KEYWORD):
                        raise ParseError(f"unexpected {self.tok.describe()} in module attributes", self.tok)
                    attributes.append(self.advance().value.upper())
                    if not self.accept_op(","):
                        break
                self.expect_op(")")
        except ParseError as exc:
            self.error(exc.message, exc.token)
            return None

        body = leading + self.parse_module_items()
        if not self.accept_kw("ENDMODULE"):
            self.error(f"expected ENDMODULE, found {self.tok.describe()}", self.tok)
        body += self.take_comments_before(len(self.text) + 1)
        if self.tok.kind is not TokenKind.EOF:
            self.error(f"unexpected {self.tok.describe()} after ENDMODULE", self.tok)
        return n.Module(self.span(start), name, tuple(attributes), tuple(body))

    def parse_module_items(self) -> list[n.ModuleItem]:
        items: list[n.ModuleItem] = []
        while True:
            items += self.take_comments_before(self.tok.start)
            if self.tok.is_kw("ENDMODULE") or self.tok.kind is TokenKind.EOF:
                return items
            start_index = self.pos
            try:
                items.append(self.module_item())
            except ParseError as exc:
                self.error(exc.message, exc.token)
                items.append(self.recover_module_item(start_index, exc))

    def module_item(self) -> n.ModuleItem:
        start = self.tok
        scope = None
        if self.accept_kw("LOCAL"):
            scope = "LOCAL"
        elif start.kind is TokenKind.IDENT and start.value.upper() == "TASK" and self.peek().is_kw("PERS", "VAR"):
            self.advance()
            scope = "TASK"

        token = self.tok
        if token.is_kw("PROC", "FUNC", "TRAP"):
            return self.routine(start, scope)
        if token.is_kw("VAR", "PERS", "CONST"):
            return self.data_decl(start, scope)
        if token.is_kw("RECORD"):
            return self.skip_to_keyword(start, "ENDRECORD", "RECORD", "user-defined RECORD types are not supported")
        if token.is_kw("ALIAS"):
            self.skip_statement()
            return self.unsupported(start, "ALIAS", "ALIAS type declarations are not supported")
        raise ParseError(f"unexpected {token.describe()} at module level", token)

    def recover_module_item(self, start_index: int, exc: ParseError) -> n.Unsupported:
        """Skip a whole routine if the error happened in one, else one declaration."""
        self.pos = start_index
        start = self.tok
        if self.tok.is_kw("LOCAL"):
            self.advance()
        end_kw = _ROUTINE_ENDS.get(self.tok.value) if self.tok.kind is TokenKind.KEYWORD else None
        if end_kw:
            return self.skip_to_keyword(start, end_kw, "SYNTAX_ERROR", exc.message)
        self.skip_statement()
        if self.pos == start_index:
            self.advance()  # always make progress
        return self.unsupported(start, "SYNTAX_ERROR", exc.message)

    def data_decl(self, start: Token, scope: str | None) -> n.DataDecl:
        storage = self.advance().value  # VAR / PERS / CONST
        type_name = self.expect_ident().text
        name = self.expect_ident().text
        dims: tuple[n.Expr, ...] = ()
        if self.accept_op("{"):
            dims = tuple(self.expr_list("}"))
            self.expect_op("}")
        init = self.expr() if self.accept_op(":=") else None
        self.expect_op(";")
        return n.DataDecl(self.span(start), storage, type_name, name, dims, init, scope)

    def routine(self, start: Token, scope: str | None) -> n.Routine:
        kind = self.advance().value  # PROC / FUNC / TRAP
        return_type = self.expect_ident().text if kind == "FUNC" else None
        name = self.expect_ident().text
        params = "" if kind == "TRAP" else self.raw_parameter_list()
        end_kw = _ROUTINE_ENDS[kind]

        body = self.block({end_kw} | _HANDLER_KEYWORDS)
        handlers = []
        while self.tok.kind is TokenKind.KEYWORD and self.tok.value in _HANDLER_KEYWORDS:
            handler_start = self.advance()
            handlers.append(
                self.skip_to_keyword(
                    handler_start,
                    end_kw,
                    f"{handler_start.value}_HANDLER",
                    f"{handler_start.value} handlers are not supported",
                    consume_end=False,
                    also_stop_at=_HANDLER_KEYWORDS,
                )
            )
        self.expect_kw(end_kw)
        return n.Routine(self.span(start), kind, name, tuple(body), params, return_type, scope, tuple(handlers))

    def raw_parameter_list(self) -> str:
        """Parameters are kept as normalised text: parameterised routines are out of V1 scope."""
        self.expect_op("(")
        first = self.tok
        depth = 1
        while depth:
            if self.tok.kind is TokenKind.EOF:
                raise ParseError("unterminated parameter list", self.tok)
            if self.tok.is_op("("):
                depth += 1
            elif self.tok.is_op(")"):
                depth -= 1
                if depth == 0:
                    break
            self.advance()
        closing = self.expect_op(")")
        raw = self.text[first.start : closing.start] if closing is not first else ""
        self.drop_comments_before(closing.start)
        return " ".join(raw.split())

    # ------------------------------------------------------------------
    # Skipping (out-of-scope constructs and error recovery)
    # ------------------------------------------------------------------

    def unsupported(self, start: Token, kind: str, reason: str) -> n.Unsupported:
        raw = self.raw_since(start)
        self.drop_comments_before(self.tokens[self.pos - 1].end if self.pos else 0)
        return n.Unsupported(self.span(start), kind, reason, raw)

    def skip_to_keyword(
        self,
        start: Token,
        end_kw: str,
        kind: str,
        reason: str,
        *,
        consume_end: bool = True,
        also_stop_at: frozenset[str] = frozenset(),
    ) -> n.Unsupported:
        while not (self.tok.is_kw(end_kw) or self.tok.kind is TokenKind.EOF):
            if self.tok.kind is TokenKind.KEYWORD and self.tok.value in also_stop_at:
                break
            self.advance()
        if self.tok.kind is TokenKind.EOF:
            self.error(f"missing {end_kw}", start)
        elif consume_end and self.tok.is_kw(end_kw):
            self.advance()
        return self.unsupported(start, kind, reason)

    def skip_statement(self) -> None:
        """Advance past exactly one statement, balancing compound blocks.

        Stops *before* a keyword that closes the enclosing block, so a broken
        statement can never swallow the ENDIF/ENDPROC of its parent.
        """
        depth = 0
        while self.tok.kind is not TokenKind.EOF:
            token = self.tok
            if token.kind is TokenKind.KEYWORD:
                if token.value in _BLOCK_OPENERS and not (token.value == "IF" and self.is_compact_if()):
                    depth += 1
                elif token.value in _BLOCK_CLOSERS and depth:
                    depth -= 1
                    self.advance()
                    if depth == 0:
                        return
                    continue
                elif token.value in _BLOCK_BOUNDARIES and depth == 0:
                    return
            if token.is_op(";") and depth == 0:
                self.advance()
                return
            self.advance()

    def is_compact_if(self) -> bool:
        """At an IF token: True for 'IF cond stmt;' (no THEN before the ';')."""
        for token in self.tokens[self.pos + 1 :]:
            if token.is_kw("THEN"):
                return False
            if token.is_op(";") or token.kind is TokenKind.EOF:
                return True
        return True

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def block(self, terminators: set[str] | frozenset[str]) -> list[n.Stmt]:
        """Statements up to (not including) one of the terminator keywords."""
        body: list[n.Stmt] = []
        while True:
            body += self.take_comments_before(self.tok.start)
            token = self.tok
            if token.kind is TokenKind.EOF:
                raise ParseError(f"unexpected end of file, expected {' / '.join(sorted(terminators))}", token)
            if token.kind is TokenKind.KEYWORD and token.value in terminators:
                return body
            if token.kind is TokenKind.KEYWORD and token.value in _BLOCK_BOUNDARIES:
                # Belongs to an enclosing construct: the structure is broken, let the parent recover.
                raise ParseError(f"unexpected {token.value}", token)
            body.append(self.statement_with_recovery())

    def statement_with_recovery(self) -> n.Stmt:
        start_index = self.pos
        try:
            return self.statement()
        except ParseError as exc:
            self.pos = start_index
            start = self.tok
            self.skip_statement()
            if self.pos == start_index:
                raise  # cannot skip anything here: the enclosing block must recover
            self.error(exc.message, exc.token)
            return self.unsupported(start, "SYNTAX_ERROR", exc.message)

    def statement(self) -> n.Stmt:
        token = self.tok
        if token.kind is TokenKind.KEYWORD:
            match token.value:
                case "IF":
                    return self.if_stmt()
                case "FOR":
                    return self.for_stmt()
                case "WHILE":
                    return self.while_stmt()
                case "TEST":
                    return self.test_stmt()
                case "RETURN":
                    self.advance()
                    value = None if self.tok.is_op(";") else self.expr()
                    self.expect_op(";")
                    return n.Return(self.span(token), value)
                case "EXIT":
                    self.advance()
                    self.expect_op(";")
                    return n.Exit(self.span(token))
                case "VAR" | "PERS" | "CONST":
                    return self.data_decl(token, None)
                case "GOTO" | "RAISE" | "RETRY" | "TRYNEXT" | "CONNECT":
                    self.skip_statement()
                    return self.unsupported(token, token.value, f"{token.value} is not supported")
            raise ParseError(f"unexpected keyword {token.value}", token)

        if token.is_op("%"):
            self.skip_statement()
            return self.unsupported(token, "LATE_BINDING", "late-binding call %...% cannot be resolved statically")

        if token.kind is TokenKind.IDENT:
            following = self.peek()
            if following.is_op(":"):
                self.advance()
                self.advance()
                return self.unsupported(token, "LABEL", "labels (GOTO targets) are not supported")
            if following.is_op(":=", ".", "{"):
                return self.assignment()
            return self.proc_call()

        raise ParseError(f"unexpected {token.describe()}", token)

    def assignment(self) -> n.Assign:
        start = self.tok
        target = self.postfix()
        self.expect_op(":=")
        value = self.expr()
        self.expect_op(";")
        return n.Assign(self.span(start), target, value)

    def proc_call(self) -> n.Stmt:
        name_tok = self.expect_ident()
        args = self.arg_list(";")
        self.expect_op(";")
        return self.specialise_call(name_tok, args)

    def specialise_call(self, name_tok: Token, args: list[n.Arg]) -> n.Stmt:
        """Turn the generic call of a V1 instruction into its typed node."""
        span = self.span(name_tok)
        upper = name_tok.text.upper()
        positional = [a.value for a in args if a.name is None and a.value is not None]
        optional = [a for a in args if a.name is not None]

        if upper in _MOVES:
            kind = _MOVES[upper]
            expected = 5 if kind is n.MoveKind.C else 4
            if len(positional) == expected:
                wobj = next((a.value for a in optional if a.name.upper() == "WOBJ" and not a.conditional), None)
                options = tuple(a for a in optional if not (a.name.upper() == "WOBJ" and not a.conditional))
                via = positional.pop(0) if kind is n.MoveKind.C else None
                to_point, speed, zone, tool = positional
                return n.Move(span, kind, to_point, speed, zone, tool, via, wobj, options)
            self.warn(f"{name_tok.text} with {len(positional)} positional arguments (expected {expected})", name_tok)
        elif upper in ("SET", "RESET"):
            if len(positional) == 1 and not optional:
                return n.SetSignal(span, positional[0], 1 if upper == "SET" else 0)
            self.warn(f"{name_tok.text} expects exactly one signal argument", name_tok)
        elif upper == "WAITTIME":
            if len(positional) == 1:
                return n.WaitTime(span, positional[0], tuple(optional))
            self.warn("WaitTime expects exactly one time argument", name_tok)

        return n.ProcCall(span, name_tok.text, tuple(args))

    def warn(self, message: str, token: Token) -> None:
        self.diagnostics.append(Diagnostic(Severity.WARNING, message + "; kept as a generic call", self.span(token)))

    def if_stmt(self) -> n.If:
        start = self.expect_kw("IF")
        condition = self.expr()
        if not self.accept_kw("THEN"):
            # Compact form: IF cond stmt;
            return n.If(self.span(start), (n.IfBranch(condition, (self.statement(),)),), compact=True)

        branches = [n.IfBranch(condition, tuple(self.block({"ELSEIF", "ELSE", "ENDIF"})))]
        while self.accept_kw("ELSEIF"):
            condition = self.expr()
            self.expect_kw("THEN")
            branches.append(n.IfBranch(condition, tuple(self.block({"ELSEIF", "ELSE", "ENDIF"}))))
        else_body: tuple[n.Stmt, ...] = ()
        if self.accept_kw("ELSE"):
            else_body = tuple(self.block({"ENDIF"}))
        self.expect_kw("ENDIF")
        return n.If(self.span(start), tuple(branches), else_body)

    def for_stmt(self) -> n.For:
        start = self.expect_kw("FOR")
        var = self.expect_ident().text
        self.expect_kw("FROM")
        first = self.expr()
        self.expect_kw("TO")
        last = self.expr()
        step = self.expr() if self.accept_kw("STEP") else None
        self.expect_kw("DO")
        body = self.block({"ENDFOR"})
        self.expect_kw("ENDFOR")
        return n.For(self.span(start), var, first, last, step, tuple(body))

    def while_stmt(self) -> n.While:
        start = self.expect_kw("WHILE")
        condition = self.expr()
        self.expect_kw("DO")
        body = self.block({"ENDWHILE"})
        self.expect_kw("ENDWHILE")
        return n.While(self.span(start), condition, tuple(body))

    def test_stmt(self) -> n.Test:
        start = self.expect_kw("TEST")
        subject = self.expr()
        cases = []
        default = None
        ends = {"CASE", "DEFAULT", "ENDTEST"}
        self.drop_comments_before(self.tok.start)
        while self.accept_kw("CASE"):
            values = self.expr_list(":")
            self.expect_op(":")
            cases.append(n.TestCase(tuple(values), tuple(self.block(ends))))
        if self.accept_kw("DEFAULT"):
            self.expect_op(":")
            default = tuple(self.block({"ENDTEST"}))
        self.expect_kw("ENDTEST")
        return n.Test(self.span(start), subject, tuple(cases), default)

    # ------------------------------------------------------------------
    # Arguments
    # ------------------------------------------------------------------

    def arg_list(self, closer: str) -> list[n.Arg]:
        """Call arguments up to (not including) `closer`.

        Positional args are comma-separated; optional args (\\Name...) may
        follow the previous argument with or without a comma.
        """
        args: list[n.Arg] = []
        while not self.tok.is_op(closer):
            if args and not self.accept_op(",") and not self.tok.is_op("\\"):
                raise ParseError(f"expected ',' or '{closer}', found {self.tok.describe()}", self.tok)
            args.append(self.arg())
        return args

    def arg(self) -> n.Arg:
        start = self.tok
        if not self.accept_op("\\"):
            return n.Arg(self.span(start), self.expr())
        name = self.expect_ident().text
        if self.accept_op(":="):
            return n.Arg(self.span(start), self.expr(), name)
        if self.accept_op("?"):
            var = self.expect_ident()
            return n.Arg(self.span(start), n.Name(self.span(var), var.text), name, conditional=True)
        return n.Arg(self.span(start), None, name)

    # ------------------------------------------------------------------
    # Expressions — RAPID precedence, lowest first:
    #   OR XOR  <  AND  <  NOT  <  relational  <  + -  <  * / DIV MOD  <  unary -
    # ------------------------------------------------------------------

    def expr_list(self, closer: str) -> list[n.Expr]:
        items = [self.expr()]
        while self.accept_op(","):
            items.append(self.expr())
        if not self.tok.is_op(closer):
            raise ParseError(f"expected ',' or '{closer}', found {self.tok.describe()}", self.tok)
        return items

    def expr(self) -> n.Expr:
        left = self.and_expr()
        while self.tok.is_kw("OR", "XOR"):
            op = self.advance()
            left = n.BinaryOp(left.span, op.value, left, self.and_expr())
        return left

    def and_expr(self) -> n.Expr:
        left = self.not_expr()
        while self.tok.is_kw("AND"):
            op = self.advance()
            left = n.BinaryOp(left.span, op.value, left, self.not_expr())
        return left

    def not_expr(self) -> n.Expr:
        if self.tok.is_kw("NOT"):
            op = self.advance()
            return n.UnaryOp(self.span(op), "NOT", self.not_expr())
        return self.relational()

    def relational(self) -> n.Expr:
        left = self.additive()
        if self.tok.is_op(*_RELATIONAL):
            op = self.advance()
            left = n.BinaryOp(left.span, op.value, left, self.additive())
        return left

    def additive(self) -> n.Expr:
        left = self.multiplicative()
        while self.tok.is_op("+", "-"):
            op = self.advance()
            left = n.BinaryOp(left.span, op.value, left, self.multiplicative())
        return left

    def multiplicative(self) -> n.Expr:
        left = self.unary()
        while self.tok.is_op("*", "/") or self.tok.is_kw("DIV", "MOD"):
            op = self.advance()
            left = n.BinaryOp(left.span, op.value, left, self.unary())
        return left

    def unary(self) -> n.Expr:
        if self.tok.is_op("-", "+"):
            op = self.advance()
            return n.UnaryOp(self.span(op), op.value, self.unary())
        return self.postfix()

    def postfix(self) -> n.Expr:
        node = self.primary()
        while True:
            if self.tok.is_op("."):
                self.advance()
                field = self.expect_ident()
                node = n.Component(node.span, node, field.text)
            elif self.tok.is_op("{"):
                self.advance()
                indices = self.expr_list("}")
                self.expect_op("}")
                node = n.Index(node.span, node, tuple(indices))
            else:
                return node

    def primary(self) -> n.Expr:
        token = self.tok
        span = self.span(token)
        if token.kind is TokenKind.NUMBER:
            self.advance()
            return n.Number(span, _number_value(token.text), token.text)
        if token.kind is TokenKind.STRING:
            self.advance()
            return n.String(span, token.value)
        if token.is_kw("TRUE", "FALSE"):
            self.advance()
            return n.Bool(span, token.value == "TRUE")
        if token.kind is TokenKind.IDENT:
            self.advance()
            if self.accept_op("("):
                args = self.arg_list(")")
                self.expect_op(")")
                return n.FuncCall(span, token.text, tuple(args))
            return n.Name(span, token.text)
        if token.is_op("("):
            self.advance()
            inner = self.expr()
            self.expect_op(")")
            return inner
        if token.is_op("["):
            self.advance()
            items = self.expr_list("]") if not self.tok.is_op("]") else []
            self.expect_op("]")
            return n.Aggregate(span, tuple(items))
        raise ParseError(f"expected an expression, found {token.describe()}", token)


def _number_value(text: str) -> int | float:
    if any(c in text for c in ".eE"):
        return float(text)
    return int(text)
