# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""`crossarm anonymize`: the zip converts as the input does, and shows nothing of it.

Equivalence: the diagnostic (tests/test_diagnose_privacy.py's oracle, crossarm.diagnose) of the input and of the
anonymized zip, extracted, are the same: programs, TODO and warnings by cause, share converted by area and per task,
RAPID instructions and functions used and converted, calls of the backup's routines by parameter types, data types,
records, control constructs, signals; and the conversions write as many points.

Privacy audit: what test_diagnose_privacy.collect finds in the input (identifiers, strings, comment words, numbers of
two digits or more, file and folder names) is not in the zip, but RAPID's vocabulary that anonymize keeps by rule
(its own names, the components of its data types after a dot, the optional arguments of its own instructions,
the ABB options), the generic TASKn folders of a backup, and numbers outside texts and comments (kept: the conversion
depends on them; positions are checked apart: every robtarget coordinate moved, unless --keep-geometry).

Inputs: the test fixtures, the backup of tests/diag_backup.py, a module written here with the tricky cases, the local
test corpus (abb/, skipped when absent) and, on the author's machine only, the local real-world corpus (skipped when
absent; never named in the repository).
"""

import json
import re
import zipfile
from pathlib import Path

import pytest
from diag_backup import make_backup
from test_diagnose_privacy import DIGITS, REAL, SYNTHETIC, VOCABULARY, _words, collect

from crossarm import anonymize, diagnose
from crossarm.cli import _build_parser, main
from crossarm.rapid import RAPID_SUFFIXES
from crossarm.rapid.lexer import tokenize
from crossarm.rapid.system_info import read_system
from crossarm.rapid.tokens import TokenKind

FIXTURES = Path(__file__).parent / "fixtures"
PICK = FIXTURES / "rapid" / "pick_and_place.mod"
COMPARED = ("conversion", "instructions", "functions", "user_calls", "data_types", "records", "aliases", "control",
            "signals")  # fmt: skip

TRICKY = """\
MODULE StationCell
  ! late binding, a field named like a RAPID component, a parameter named like an optional argument
  RECORD cellSpot
    num x;
    num heightMm;
  ENDRECORD
  CONST robtarget pHomeLeft := [[612.25,-104.5,880.75],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
  CONST robtarget pZero := [[0,0,0],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
  PERS wobjdata wFixtureNorth := [FALSE,TRUE,"",[[1200.5,350.25,40],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  PERS tooldata tSuctionCup := [TRUE,[[0,0,155.5],[1,0,0,0]],[1.2,[0,0,40],[1,0,0,0],0,0,0]];
  VAR cellSpot spotNorth := [12,34];
  VAR string sNextStation := "Station_";
  VAR num nStation := 2;
  VAR num nCount;

  PROC main()
    FOR k FROM 1 TO 3 DO
      CallByVar "Station_", k;
    ENDFOR
    %"Station_" + NumToStr(nStation, 0)%;
    %"cleanNozzle"%;
    moveTo pHomeLeft \\WObj:=wFixtureNorth;
    IF nCount > 3 moveTo pHomeLeft;
    nCount := spotNorth.x + spotNorth.heightMm;
    TPWrite "Brandaris's line; done";
    TPWrite "Ab";
    TPWrite ",";
  ERROR
    ! retry; then stop
    TPWrite "Ü at Brandaris";
    RETRY;
  ENDPROC

  PROC moveTo(robtarget target, \\PERS wobjdata WObj)
    IF Present(WObj) THEN
      MoveL target, v500, fine, tSuctionCup \\WObj:=WObj;
    ELSE
      MoveL target, v500, z10, tSuctionCup;
    ENDIF
    MoveL pZero, v100, fine, tSuctionCup \\WObj:=wFixtureNorth;
  ENDPROC

  PROC Station_1()
    SetDO doSuctionNorth, 1;
  ENDPROC

  PROC Station_2()
    SetDO doSuctionNorth, 0;
  ENDPROC

  PROC Station_3()
    WaitDI diPartPresentNorth, 1;
  ENDPROC

  PROC cleanNozzle()
    TPWrite "Nozzle cleaned at 1287";
  ENDPROC
ENDMODULE
"""


def _tricky(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "StationCell.mod"
    path.write_text(TRICKY, encoding="utf-8")
    return path


def _input(name, tmp_path: Path) -> Path:
    if name == "diag_backup":
        return make_backup(tmp_path / "in")
    if name == "tricky":
        return _tricky(tmp_path / "in")
    return name


def _extract(result: anonymize.Anonymized, folder: Path) -> Path:
    archive = folder / "anonymized.zip"
    anonymize.write(result, archive)
    target = folder / "anonymized"
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(target)
    return target


def _diagnostic(path: Path, monkeypatch) -> tuple[dict, int]:
    """The diagnostic's parts the anonymization must keep, and the points the conversion writes."""
    real_run = diagnose.pipeline.run
    outputs = []

    def run(*args, **kwargs):
        outputs.append(real_run(*args, **kwargs))
        return outputs[-1]

    monkeypatch.setattr(diagnose.pipeline, "run", run)
    diag = diagnose.diagnose([path])
    points = sum(len(info.points) for out in outputs for task in out.tasks if task.result
                 for info in task.result.programs)  # fmt: skip
    kept = {key: diag[key] for key in COMPARED}
    kept["input"] = {k: v for k, v in diag["input"].items() if k != "kind"}
    return kept, points


def differences(a: object, b: object, where: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        return [d for k in sorted(set(a) | set(b), key=str) for d in differences(a.get(k), b.get(k), f"{where}.{k}")]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b, strict=True)) for d in differences(x, y, f"{where}[{i}]")]
    return [] if a == b else [f"{where}: {a!r} -> {b!r}"]


# ---------------------------------------------------------------------------
# Privacy audit of the zip
# ---------------------------------------------------------------------------

ANONYMIZE_WORDS = (
    _words(Path(anonymize.__file__).read_text(encoding="utf-8")) | _words(" ".join(anonymize.NATIVE_NAMES))
    | _words(" ".join(anonymize.NATIVE_COMPONENTS)) | _words(" ".join(RAPID_SUFFIXES))
)  # fmt: skip


def _routines(tokens) -> set[str]:
    out = set()
    for i, token in enumerate(tokens[:-2]):
        if token.is_kw("PROC", "TRAP") and tokens[i + 1].kind is TokenKind.IDENT:
            out.add(tokens[i + 1].value.lower())
        elif token.is_kw("FUNC") and tokens[i + 2].kind is TokenKind.IDENT:
            out.add(tokens[i + 2].value.lower())
    return out


def _native_arguments(texts: list[str]) -> set[str]:
    """The \\X optional arguments of the input given in a statement that is not a call of the input's own routines:
    RAPID's vocabulary (\\WObj, \\Conc...), kept by anonymize."""
    lexed = [[t for t in tokenize(text).tokens if t.kind is not TokenKind.EOF] for text in texts]
    routines = set().union(*(_routines(tokens) for tokens in lexed)) if lexed else set()
    out = set()
    for tokens in lexed:
        head = None
        header_ends = set()  # the ) closing a routine's parameters, the name of a TRAP: a statement follows
        for i, token in enumerate(tokens):
            if token.is_kw("TRAP") and i + 1 < len(tokens):
                header_ends.add(i + 1)
            elif token.is_kw("PROC", "FUNC"):
                closing = next((j for j in range(i, len(tokens)) if tokens[j].is_op(")")), None)
                if closing is not None:
                    header_ends.add(closing)
            if i == 0 or tokens[i - 1].is_op(";") or i - 1 in header_ends or (
                    tokens[i - 1].kind is TokenKind.KEYWORD and not tokens[i - 1].is_kw("PROC", "FUNC", "TRAP")):
                head = token.value.lower() if token.kind is TokenKind.IDENT else None
            if token.kind is TokenKind.IDENT and i and tokens[i - 1].is_op("\\") and head not in routines:
                out.add(token.value.lower())
    return out


def _robtargets(texts: dict[str, str]) -> dict[str, list[tuple[float, ...]]]:
    """Each robtarget declared with a value: its x, y, z (one per element of an array)."""
    out: dict[str, list[tuple[float, ...]]] = {}
    for text in texts.values():
        file = anonymize._File(0, False, ".mod", text)
        file.tokens = tokenize(text).tokens
        anonymize._Reader(file, lambda *args, **kwargs: None).run()
        for decl in file.decls:
            if decl.type_name == "ROBTARGET":
                poses = anonymize._poses(file.tokens, decl.start, decl.end)
                out.setdefault(decl.name, []).extend(tuple(p[2] for p in parts) for parts in poses)
    return out


def _numbers_not_moved(text: str) -> set[str]:
    file = anonymize._File(0, False, ".mod", text)
    file.tokens = tokenize(text).tokens
    anonymize._Reader(file, lambda *args, **kwargs: None).run()
    posed = {i for decl in file.decls if decl.type_name in ("ROBTARGET", "WOBJDATA", "TOOLDATA")
             for i in range(decl.start, decl.end)}  # fmt: skip
    return {t.text for i, t in enumerate(file.tokens) if t.kind is TokenKind.NUMBER and i not in posed}


def _rapid_texts(path: Path) -> dict[str, str]:
    files = [p for p in path.rglob("*")] if path.is_dir() else [path]
    from crossarm.rapid.source import read_source

    return {str(f): read_source(f).text for f in files if f.is_file() and f.suffix.lower() in RAPID_SUFFIXES}


def audit(path: Path, result: anonymize.Anonymized, keep_geometry: bool = False) -> list[str]:
    """What of `path` the anonymized zip shows (should be nothing)."""
    secrets = collect(path)
    contents = {name: data.decode("utf-8") for name, data in result.files.items()}
    everything = "\n".join([*contents, *contents.values()])
    rapid_in = _rapid_texts(path)
    rapid_out = {name: text for name, text in contents.items() if Path(name).suffix.lower() in RAPID_SUFFIXES}
    root = next((p.parent for p in path.rglob("RAPID") if p.is_dir()), None) if path.is_dir() else None
    system = read_system(root)
    allowed = VOCABULARY | ANONYMIZE_WORDS | _native_arguments(list(rapid_in.values()))
    allowed |= _words(" ".join([system.robotware or "", *system.options, *system.robots]))
    allowed |= {w for w in _words(everything) if re.fullmatch(r"task\d+", w)}  # a backup's generic task folders
    allowed |= {w for text in rapid_out.values() for t in tokenize(text).tokens if t.kind is TokenKind.NUMBER
                for w in _words(t.text)}  # 0x01, 9E+09: numbers in the code, kept  # fmt: skip
    found = [f"word {w}" for w in sorted((secrets.words & _words(everything)) - allowed)]
    found += [f"string {s!r}" for s in sorted(secrets.strings) if s.upper() not in anonymize.NATIVE_NAMES
              and re.search(r"(?<!\w)" + re.escape(s) + r"(?!\w)", everything)]  # fmt: skip

    strings_in = {t.value for text in rapid_in.values() for t in tokenize(text).tokens if t.kind is TokenKind.STRING}
    out_tokens = [t for text in rapid_out.values() for t in tokenize(text).tokens]
    identifiers = {t.value for t in out_tokens if t.kind is TokenKind.IDENT}
    strings_out = {t.value for t in out_tokens if t.kind is TokenKind.STRING}
    found += [f"text {s!r}" for s in sorted(strings_in & strings_out) if any(c.isalpha() for c in s)]
    comments = [c.text for text in rapid_out.values() for c in tokenize(text).comments]
    found += [f"comment {c!r}" for c in comments if c.strip(";")]

    in_code = {d for text in rapid_in.values() for t in tokenize(text).tokens if t.kind is TokenKind.NUMBER
               for d in DIGITS.findall(t.text)}  # fmt: skip
    # numbers as written, out of the positions moved: a random offset may give any digits by chance
    out_numbers = {d for text in rapid_out.values() for d in _numbers_not_moved(text)}
    out_numbers |= {d for s in strings_out - identifiers for d in DIGITS.findall(s)}
    found += [f"number {d}" for d in sorted((secrets.numbers - in_code) & out_numbers)]

    new_names = {k.upper(): v.upper() for k, v in result.mapping["names"].items()}
    before, after = _robtargets(rapid_in), _robtargets(rapid_out)
    for name, points in before.items():
        moved = after.get(new_names.get(name, name), [])
        for old, new in zip(points, moved, strict=False):
            if keep_geometry and old != new:
                found.append(f"position of {name} changed")
            elif not keep_geometry and any(o == n_ for o, n_ in zip(old, new, strict=True)) and any(old):
                found.append(f"position of {name} kept")
    return found


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def check(path: Path, tmp_path: Path, monkeypatch) -> list[str]:
    result = anonymize.anonymize([path], seed=11)
    original, points = _diagnostic(path, monkeypatch)
    again, points_again = _diagnostic(_extract(result, tmp_path), monkeypatch)
    problems = differences(original, again)
    if points != points_again:
        problems.append(f"points: {points} -> {points_again}")
    return problems + audit(path, result)


FIXTURE_INPUTS = [*sorted(FIXTURES.glob("rapid/*.mod")), "diag_backup", "tricky"]


@pytest.mark.parametrize("name", FIXTURE_INPUTS, ids=lambda p: getattr(p, "name", p))
def test_a_fixture_converts_the_same_and_shows_nothing(name, tmp_path, monkeypatch):
    assert check(_input(name, tmp_path), tmp_path, monkeypatch) == []


@pytest.mark.skipif(not SYNTHETIC, reason="no local test corpus")
@pytest.mark.parametrize("path", SYNTHETIC, ids=lambda p: p.name)
def test_the_local_test_corpus_converts_the_same_and_shows_nothing(path, tmp_path, monkeypatch):
    assert check(path, tmp_path, monkeypatch) == []


@pytest.mark.skipif(not REAL, reason="local only")
def test_the_local_real_world_corpus_converts_the_same_and_shows_nothing(tmp_path, monkeypatch):
    problems = []
    for number, path in enumerate(REAL):
        problems += [f"input {number}: {item}" for item in check(path, tmp_path / str(number), monkeypatch)]
    assert not problems, problems


def test_the_audit_sees_a_leak(tmp_path):
    path = make_backup(tmp_path / "in")
    result = anonymize.anonymize([path], seed=1)
    name = "RAPID/TASK1/PROGMOD/MOD_2.mod"
    text = result.files[name].decode("utf-8")
    result.files[name] = text.replace("NUM_2", "beadCounter").replace('"SC______"', '"Hendrika"').encode("utf-8")
    found = audit(path, result)
    assert "word beadcounter" in found
    assert "text 'Hendrika'" in found


def test_the_same_seed_gives_the_same_bytes(tmp_path):
    path = make_backup(tmp_path / "in")
    first = anonymize.anonymize([path], seed=5).zip_bytes()
    assert anonymize.anonymize([path], seed=5).zip_bytes() == first
    assert anonymize.anonymize([path], seed=6).zip_bytes() != first


def test_the_zip_holds_only_what_crossarm_reads(tmp_path):
    result = anonymize.anonymize([make_backup(tmp_path / "in")], seed=1)
    assert sorted(result.files) == ["BACKINFO/backinfo.txt", "RAPID/TASK1/PROGMOD/MOD_2.mod",
                                    "RAPID/TASK1/SYSMOD/MOD_1.sys", "SYSPAR/EIO.cfg", anonymize.REPORT]  # fmt: skip
    archive = anonymize.write(result, tmp_path / "out.zip")
    with zipfile.ZipFile(archive) as zipped:
        assert {info.date_time for info in zipped.infolist()} == {(1980, 1, 1, 0, 0, 0)}
    report = result.report
    assert anonymize.LIMIT in report
    assert "Comments removed: 3" in report
    assert "seed" not in report.lower()


def test_keep_geometry_and_scramble_tools(tmp_path):
    path = make_backup(tmp_path / "in")
    kept = anonymize.anonymize([path], seed=1, keep_geometry=True)
    text = kept.files["RAPID/TASK1/PROGMOD/MOD_2.mod"].decode("utf-8")
    assert "[[1287.45,-342.18,915.6]" in text and "[[640,-1180,455]" in text
    assert audit(path, kept, keep_geometry=True) == []
    moved = anonymize.anonymize([path], seed=1, scramble_tools=True)
    text = moved.files["RAPID/TASK1/PROGMOD/MOD_2.mod"].decode("utf-8")
    assert "[[18.4,0,236.75]" not in text
    assert "[[18.4,0,236.75]" in anonymize.anonymize([path], seed=1).files["RAPID/TASK1/PROGMOD/MOD_2.mod"].decode()


def test_the_late_bound_names_and_rapid_vocabulary(tmp_path):
    result = anonymize.anonymize([_tricky(tmp_path)], seed=1)
    [text] = [v.decode("utf-8") for k, v in result.files.items() if k.endswith(".mod")]
    assert 'CallByVar "LBA_", IDX_1;' in text
    assert 'PROC LBA_1()' in text and '%"LBA_" + NumToStr(NUM_1, 0)%' in text
    assert "\\WObj:=WObj" not in text and "\\WObj:=PARAM_2" in text  # RAPID's \WObj kept, the parameter renamed
    assert "DATA_1.x + DATA_1.FIELD_1" in text  # a field named like pos.x keeps its name
    assert re.search(r'TPWrite "S\w_+\'?;";', text)  # length, apostrophe and semicolon kept
    assert 'TPWrite ",";' in text
    assert "!;" in text  # a comment's semicolons are kept, as the coverage counts them in an error handler


def test_write_mapping_is_outside_the_zip(tmp_path, capsys):
    source = make_backup(tmp_path / "in")
    archive, table = tmp_path / "a.zip", tmp_path / "table.json"
    assert main(["anonymize", str(source), "-o", str(archive), "--seed", "3", "--write-mapping", str(table)]) == 0
    mapping = json.loads(table.read_text(encoding="utf-8"))
    assert mapping["names"]["beadCounter"].startswith("NUM_")
    assert mapping["warning"] == anonymize.MAPPING_WARNING
    with zipfile.ZipFile(archive) as zipped:
        body = b"".join(zipped.read(n) for n in zipped.namelist()).decode("utf-8")
    assert "beadCounter" not in body and "frame_offsets" not in body
    out = capsys.readouterr().out
    assert "never send it" in out.lower() and "--keep-geometry" in out


def test_the_command_default_output_and_errors(tmp_path, capsys):
    source = tmp_path / "Customer_Cell.mod"
    source.write_text(PICK.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["anonymize", str(source)]) == 0
    assert (tmp_path / "crossarm_anonymized.zip").is_file()
    assert main(["anonymize", str(source)]) == 0
    assert (tmp_path / "crossarm_anonymized_2.zip").is_file()
    assert main(["anonymize", str(tmp_path / "missing.mod")]) == 2


def test_the_help_states_the_joint_position_limit():
    parser = _build_parser()
    action = next(a for a in parser._subparsers._actions if a.choices and "anonymize" in a.choices)
    text = " ".join(action.choices["anonymize"].format_help().split())
    assert "cannot be used to check paths in ROBOGUIDE unless it is made with --keep-geometry" in text
