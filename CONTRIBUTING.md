# Contributing

Bug reports and test cases are very welcome — open an issue.

The single most useful thing you can send is a **RAPID construct CrossArm does
not convert**, together with what the FANUC controller should produce for it.
That is what drives the roadmap, and it is what every measured improvement so
far has come from.

**Please never attach a backup you are not free to share.** Strip names, coordinates, IP
addresses and module names first, or describe the construct in the abstract.
A three-line example is usually enough.

## Code contributions

CrossArm is licensed under the [Business Source License 1.1](LICENSE), with a
commercial licence available for production use (see
[LICENSING.md](LICENSING.md)).

There is currently a single contributor, and no contributor agreement is in
place. **Code contributions may therefore be subject to licence terms defined
later**, so that the project keeps the option of offering a commercial licence
covering the whole of the code.

If you would like to send code, please open an issue first so we can settle
that point before you spend time on it. Describing the change in an issue is a
perfectly good contribution on its own, and it keeps the licensing clean for
both of us.

## Running the tests

```bash
pip install -e ".[dev]"
pytest -q
ruff check src tests
```

Everything runs offline. Tests on a local corpus of controller backups are
skipped unless `CROSSARM_RAPID_CORPUS` points at one.

```bash
CROSSARM_RAPID_CORPUS=/path/to/rapid CROSSARM_FANUC_CORPUS=/path/to/fanuc pytest
                                                   # + a local corpus of backups (not in the repo)
CROSSARM_UPDATE_GOLDEN=1 pytest                     # regenerate expected outputs, then review the diff
python tools/corpus_snapshot.py check              # what changed on the local corpus (kept outside the repo)
python tools/corpus_snapshot.py check <folder> <snapshot.json>   # another corpus, one snapshot each
```

`corpus_snapshot.py` takes a folder of backups or of folders of loose RAPID modules, and compares
coverage by area, TODO in all and for each cause, warnings, syntax errors and a fingerprint of every
program written.

## Running the controller probes

The probes behind [docs/validation.md](docs/validation.md) run on the simulators, with nobody at
either pendant:

```bash
python tools/probe_all.py                          # every controller probe, on ROBOGUIDE and RobotStudio
python tools/check_conventions.py run | check      # axis conventions on the robots loaded now
python tools/probe_motion.py run | fit | check      # speeds and zones, measured on both simulators
python tools/make_path_probe.py run | check         # the path where zones matter, on both simulators
```

`probe_all.py` loads the probe programs by FTP, runs them through the FANUC COM interface and reads
the registers from the robot's web pages: a ROBOGUIDE cell with its virtual pendant switched off, on
the same machine, one cell open at a time. It overwrites frames and registers: use a test cell. The
ABB probes need a RobotStudio station with `tools/CrossArmServer.mod` loaded in T_ROB1 and started
from `main`; without it they are skipped.

## Layout

```
src/crossarm/
  cli.py                 crossarm parse / stats / convert
  app.py, gui.py         desktop application (Tkinter) and CrossArm.exe entry point
  summary.py             what the window says, in plain words (tested without a display)
  backup.py, pipeline.py backup / zip / files detection, conversion per task, output folder
  geometry.py            quaternion <-> matrix <-> W,P,R, Offs, RelTool
  rapid/                 lexer, parser, AST, EIO.cfg reader, JSON/pseudo-code output
  convert/               data evaluation, confdata -> CONFIG, speeds and zones, RAPID -> TP, report
  fanuc/                 TP program model, .LS writer and lossless parser, numbers used on a controller
tools/                   controller probes (make_*_probe.py), the ROBOGUIDE and RobotStudio runners
                         (roboguide.py, robotstudio.py and CrossArmServer.mod, probe_all.py),
                         corpus_snapshot.py, tp_forms.py, icon and preview generators
packaging/               CrossArm.exe entry script, icon and release notes (built by .github/workflows/release.yml)
tests/
  rapid/ convert/ fanuc/ unit, golden, round-trip and local-corpus tests
  fixtures/rapid/        synthetic RAPID sources
  fixtures/fanuc/        expected output + ROBOGUIDE re-exports
  fixtures/probes/       probe programs and measurements from both controllers
docs/                    user guide, validation, design notes, RAPID grammar, .LS format status
```
