# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Corrupted RAPID never crashes the parser or the converter.

Each case mutates a module a little — a token inserted, a few characters deleted,
a line duplicated or moved — then parses and converts it. The parser must recover and
the converter must refuse what it cannot read (TODO), never raise. Seeded, so a failure
replays exactly. Runs on the committed demo programs in CI, and on a local corpus
when one is present (CROSSARM_RAPID_CORPUS, default ./abb; nothing is written).
"""

import os
import random
from datetime import datetime
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.translate import Blocker
from crossarm.rapid import RAPID_SUFFIXES, parse_text

TOKENS = [";", ",", ":=", "[", "]", "(", ")", "\\", "MoveL", "Offs(", "RelTool(", "IF", "THEN", "ENDIF", "FOR",
          "WHILE", "ENDWHILE", "TEST", "CASE", "0", "-1", "9E9", '"x"', "TRUE", "PERS", "VAR", "CONST", "!", "{1}",
          ".trans", "fine", "z10", "v100", "tool0", "wobj0", "*", "/", "DIV", "0.0", "1E400", "WaitDI", "Set"]  # fmt: skip

_REPO = Path(__file__).resolve().parents[2]
_CORPUS = Path(os.environ.get("CROSSARM_RAPID_CORPUS", _REPO / "abb"))


def read(path: Path) -> str:
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def mutate(text: str, rng: random.Random) -> str:
    lines = text.split("\n")
    for _ in range(rng.randint(1, 3)):
        i = rng.randrange(len(lines))
        line = lines[i]
        op = rng.choice(["insert", "delete", "duplicate", "swap"])
        if op == "insert":
            at = rng.randint(0, len(line))
            lines[i] = line[:at] + rng.choice(TOKENS) + line[at:]
        elif op == "delete" and line:
            at = rng.randrange(len(line))
            lines[i] = line[:at] + line[at + rng.randint(1, 4) :]
        elif op == "duplicate":
            lines.insert(i, line)
        elif op == "swap":
            j = rng.randrange(len(lines))
            lines[i], lines[j] = lines[j], lines[i]
    return "\n".join(lines)


def crashes(sources: list[str], runs: int, seed: int) -> list[str]:
    """Exceptions, and internal errors the converter caught: both are bugs in crossarm."""
    rng = random.Random(seed)
    found = []
    for n in range(runs):
        source = mutate(rng.choice(sources), rng)
        try:
            parsed = parse_text(source)
            if parsed.module is not None:
                result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)),
                                 sources={parsed.module.name: source})  # fmt: skip
                found += [f"case {n} (seed {seed}): {note.message}"
                          for note in result.notes if note.category == Blocker.INTERNAL]  # fmt: skip
        except Exception as exc:  # noqa: BLE001 - any exception is the finding
            found.append(f"case {n} (seed {seed}): {type(exc).__name__}: {exc}")
    return found


def test_corrupted_demo_programs_never_crash():
    sources = [read(p) for p in sorted((FIXTURES / "rapid").glob("*.mod"))]
    assert crashes(sources, runs=400, seed=20260923) == []


CORPUS = sorted(p for p in _CORPUS.rglob("*") if p.suffix.lower() in RAPID_SUFFIXES) if _CORPUS.is_dir() else []


@pytest.mark.skipif(not CORPUS, reason="no RAPID corpus (set CROSSARM_RAPID_CORPUS)")
def test_corrupted_corpus_modules_never_crash():
    sources = [read(p) for p in CORPUS]
    assert crashes(sources, runs=800, seed=7) == []


# Whole files damaged as a copy or an editor damages them, converted with the others through the complete pipeline
# (reading, parsing, every task, the reports). CROSSARM_FUZZ_RUNS raises the number of cases (default: a few
# seconds in CI), CROSSARM_FUZZ_SEED changes the seed.
FUZZ_RUNS = int(os.environ.get("CROSSARM_FUZZ_RUNS", "60"))
FUZZ_SEED = int(os.environ.get("CROSSARM_FUZZ_SEED", "20261012"))


def damage(data: bytes, rng: random.Random) -> bytes:
    text = data.decode("utf-8", errors="replace")
    match rng.choice(["edit", "edit", "truncate", "cp1252", "bom", "utf16", "line_ends", "empty", "binary", "nul",
                      "no_end", "deep"]):  # fmt: skip
        case "edit":
            return mutate(text, rng).encode("utf-8")
        case "truncate":
            return data[: rng.randrange(max(1, len(data)))]
        case "cp1252":
            return text.replace("\n", ' ! àéèç°µ€\n', 3).encode("cp1252", errors="replace")
        case "bom":
            return b"\xef\xbb\xbf" + data
        case "utf16":
            return text.encode("utf-16")
        case "line_ends":
            return "".join(line + rng.choice(["\r\n", "\n", "\r"]) for line in text.split("\n")).encode("utf-8")
        case "empty":
            return b""
        case "binary":
            return rng.randbytes(rng.randint(1, 2000))
        case "nul":
            at = rng.randrange(max(1, len(data)))
            return data[:at] + b"\x00" * rng.randint(1, 20) + data[at:]
        case "no_end":
            return text.replace("ENDMODULE", "").encode("utf-8")
        case _:
            lines = text.split("\n")
            lines.insert(rng.randrange(len(lines)), "x := " + "(" * 500 + "1" + ")" * 500 + "+1" * 3000 + ";")
            return "\n".join(lines).encode("utf-8")


def pipeline_crashes(files: list[Path], runs: int, seed: int, folder: Path) -> list[str]:
    from crossarm import pipeline

    rng = random.Random(seed)
    found = []
    for case in range(runs):
        work = folder / f"case{case}"
        work.mkdir()
        for path in files:
            (work / path.name).write_bytes(path.read_bytes())
        for _ in range(rng.randint(1, 2)):
            target = work / rng.choice(files).name
            target.write_bytes(damage(target.read_bytes(), rng))
        try:
            out = pipeline.run([work], folder / f"out{case}", log=lambda _line: None)
            found += [f"case {case} (seed {seed}): {note.message}" for task in out.tasks if task.result
                      for note in task.result.notes if note.category == Blocker.INTERNAL]  # fmt: skip
        except ValueError:  # every module unreadable: said, as the command line says it
            pass
        except Exception as exc:  # noqa: BLE001 - any other exception is the finding
            found.append(f"case {case} (seed {seed}): {type(exc).__name__}: {exc}")
    return found


def test_damaged_files_never_stop_the_conversion(tmp_path):
    files = sorted((FIXTURES / "rapid").glob("*.mod"))
    assert pipeline_crashes(files, FUZZ_RUNS, FUZZ_SEED, tmp_path) == []
