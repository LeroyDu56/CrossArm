# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Privacy audit of `crossarm diagnose`: nothing of the input reaches crossarm_diag.json or crossarm_diag.md.

From each input, every identifier, string, comment word, number of two digits or more, file, folder, task, signal
and device name is collected (the RAPID through CrossArm's lexer, EIO.cfg every attribute, backinfo.txt and
system.xml every word); none may appear in the diagnostic, compared token by token (a word is a whole identifier,
not a substring), except the diagnostic's own vocabulary: RAPID's reserved words and its own instructions, functions
and data types, the causes of the report, the words of diagnose.py itself (keys, headings), and the system section
(ABB option names and codes, kept by design). A user identifier equal to one of those words cannot be told apart from
the vocabulary: that is the limit of this audit.

Numbers: the diagnostic's counters may equal a number of the input by chance, so numbers are checked in the JSON's
strings only (keys and text values), not in its typed counters, and not in the environment, the system section or
where in CrossArm an error happened, nor the CrossArm version. The .md is made from the JSON alone (diagnose.markdown takes only the dict).

Inputs: the test fixtures (and the backup of tests/diag_backup.py), the local test corpus (abb/, skipped when absent) and, on the author's machine only, the
local real-world corpus (skipped when absent; never named in the repository).
"""

import json
import re
from pathlib import Path

import pytest
from diag_backup import make_backup

from crossarm import diagnose
from crossarm.convert import blockers, coverage
from crossarm.rapid import RAPID_SUFFIXES
from crossarm.rapid.eio import eio_records
from crossarm.rapid.lexer import tokenize
from crossarm.rapid.source import read_source
from crossarm.rapid.tokens import RESERVED_WORDS, TokenKind

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
WORD = re.compile(r"[^\W\d]\w*")
DIGITS = re.compile(r"\d{2,}")


def _words(text: str) -> set[str]:
    return {w.lower() for w in WORD.findall(text)}


VOCABULARY = (
    _words(" ".join(RESERVED_WORDS)) | _words(" ".join(diagnose.RAPID_INSTRUCTIONS))
    | _words(" ".join(diagnose.NATIVE_FUNCTIONS)) | _words(" ".join(diagnose.NATIVE_TYPES))
    | _words(Path(diagnose.__file__).read_text(encoding="utf-8"))
    | _words(Path(blockers.__file__).read_text(encoding="utf-8"))
    | _words(" ".join(coverage.AREAS)) | _words("ready workable not empty")
)  # fmt: skip


class Secrets:
    def __init__(self) -> None:
        self.words: set[str] = set()
        self.strings: set[str] = set()
        self.numbers: set[str] = set()
        self.counted = 0

    def text(self, text: str) -> None:
        self.words |= _words(text)
        self.numbers |= set(DIGITS.findall(text))

    def rapid(self, text: str) -> None:
        lexed = tokenize(text)
        for token in lexed.tokens:
            if token.kind is TokenKind.IDENT:
                self.words.add(token.value.lower())
            elif token.kind is TokenKind.STRING:
                self.text(token.value)
                if len(token.value) >= 6 and _words(token.value) - VOCABULARY:
                    self.strings.add(token.value)
            elif token.kind is TokenKind.NUMBER:
                self.numbers |= set(DIGITS.findall(token.text))
        for comment in lexed.comments:
            self.text(comment.text)


def collect(path: Path) -> Secrets:
    """Everything of the input a diagnostic must not show."""
    found = Secrets()
    found.text(" ".join(path.resolve().parts))
    files = [p for p in path.rglob("*")] if path.is_dir() else [path]
    for file in files:
        found.text(" ".join(file.relative_to(path).parts) if path.is_dir() else file.name)
        if not file.is_file():
            continue
        suffix = file.suffix.lower()
        if suffix in RAPID_SUFFIXES:
            found.rapid(read_source(file).text)
        elif suffix == ".cfg":
            for _section, attrs in eio_records(read_source(file).text):
                found.text(" ".join(attrs.values()))
        elif file.name.lower() in ("backinfo.txt", "system.xml"):
            found.text(file.read_text(encoding="utf-8", errors="replace"))
    found.words -= VOCABULARY
    found.counted = len(found.words) + len(found.strings) + len(found.numbers)
    return found


def _strings(data: object, skip: frozenset[str] = frozenset({"crossarm", "environment", "system", "where"})) -> list[str]:
    """Every key and text value of the diagnostic, but those of the skipped keys."""
    out: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in skip:
                continue
            out.append(str(key))
            out += _strings(value, skip)
    elif isinstance(data, list):
        for value in data:
            out += _strings(value, skip)
    elif isinstance(data, str):
        out.append(data)
    return out


def leaks(path: Path, tmp_path: Path) -> tuple[list[str], int]:
    """What of `path` its diagnostic shows (should be nothing), and how many values were checked."""
    diag = diagnose.diagnose([path])
    as_json, as_md = diagnose.write(diag, tmp_path / "diag")
    text = as_json.read_text(encoding="utf-8") + as_md.read_text(encoding="utf-8")
    secrets = collect(path)
    allowed = _words(json.dumps(diag["system"])) | _words(json.dumps(diag["environment"]))
    allowed |= {w for e in diag["internal_errors"] for w in _words(e["type"] + " " + e["where"])}
    found = [f"word {w}" for w in sorted((secrets.words & _words(text)) - allowed)]
    found += [f"string {s!r}" for s in sorted(secrets.strings) if s in text]
    numbers = {d for s in _strings(diag) for d in DIGITS.findall(s)}
    found += [f"number {d}" for d in sorted(secrets.numbers & numbers)]
    return found, secrets.counted


FIXTURE_INPUTS = [*sorted(FIXTURES.glob("rapid/*.mod")), "diag_backup"]  # the backup is written by the test


@pytest.mark.parametrize("path", FIXTURE_INPUTS, ids=lambda p: getattr(p, "name", p))
def test_a_diagnostic_shows_nothing_of_a_fixture(path, tmp_path):
    found, checked = leaks(make_backup(tmp_path / "in") if path == "diag_backup" else path, tmp_path)
    assert checked > 20
    assert not found, found


def _corpus(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith("_")
                  and any(f.suffix.lower() in RAPID_SUFFIXES for f in p.rglob("*")))  # fmt: skip


SYNTHETIC = _corpus(ROOT / "abb")
REAL = _corpus(ROOT / "local" / "real_world")


@pytest.mark.skipif(not SYNTHETIC, reason="no local test corpus")
@pytest.mark.parametrize("path", SYNTHETIC, ids=lambda p: p.name)
def test_a_diagnostic_shows_nothing_of_the_local_test_corpus(path, tmp_path):
    found, checked = leaks(path, tmp_path)
    assert checked > 100
    assert not found, found


@pytest.mark.skipif(not REAL, reason="local only")
def test_a_diagnostic_shows_nothing_of_the_local_real_world_corpus(tmp_path):
    problems = []
    for number, path in enumerate(REAL):
        found, _checked = leaks(path, tmp_path / str(number))
        problems += [f"input {number}: {item}" for item in found]
    assert not problems, problems


def test_the_markdown_is_made_from_the_json_alone(tmp_path):
    diag = diagnose.diagnose([make_backup(tmp_path)])
    again = json.loads(json.dumps(diag))
    assert diagnose.markdown(again) == diagnose.markdown(diag)


def test_the_audit_sees_a_leak(tmp_path, monkeypatch):
    real = diagnose.diagnose

    def leaky(paths, *args, **kwargs):
        diag = real(paths, *args, **kwargs)
        diag["records"] = {"paneSpec": ["num"]}  # a record name of the input
        diag["user_calls"]["user_proc/1287"] = diag["user_calls"].pop(next(iter(diag["user_calls"])))  # a number of it
        return diag

    monkeypatch.setattr(diagnose, "diagnose", leaky)
    found, _checked = leaks(make_backup(tmp_path / "in"), tmp_path)
    assert found == ["word panespec", "number 1287"]
