# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Desktop window (Tkinter, part of Python: no extra dependency).

Written for someone who has never seen CrossArm and will not read a log:

  1. ABB program to convert       required: each choice says what CrossArm found in it
  2. FANUC robot it will run on   optional: its numbers already in use are left free
  3. Your numbering               optional: a mapping file edited from a previous run
  -> Convert                      nothing starts before the user asks

The right-hand panel first explains what the conversion produces, then shows the
result in plain words — how many programs are ready, what needs attention first —
with the report one click away. The technical log is kept in a separate window.

Inputs are inspected and converted in a background thread so the window never
freezes. Files dropped on the CrossArm.exe icon arrive as arguments (see app.py):
they are inspected and converted straight away.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from crossarm import __version__, pipeline
from crossarm._icon import PNG as ICON_PNG
from crossarm.convert import ConversionConfig
from crossarm.convert.coverage import fmt_percent
from crossarm.fanuc.usage import is_fanuc_input, read_controller
from crossarm.licence import LICENCE_FILE, LicenceStatus, licence_folder, read_licence
from crossarm.licence import current as current_licence
from crossarm.rapid import RAPID_SUFFIXES
from crossarm.summary import GOOD, INFO, WARN, describe_controller, describe_source, plural, summarize
from crossarm.support import write_error_report

RAPID_PATTERNS = " ".join(f"*{s}" for s in sorted(RAPID_SUFFIXES))

HEADER_BG = "#1F2A44"
HEADER_SUB = "#B8C2D6"
BODY_BG = "#F3F4F6"
CARD_BG = "#FFFFFF"
CARD_EDGE = "#DDE1E7"
TEXT = "#1F2937"
MUTED = "#6B7280"
OK = "#157347"
FAIL = "#B42318"
AMBER = "#9A6700"  # not WARN: that name is the summary's warning level
EVALUATION = "#F2C94C"  # the evaluation-copy mark, readable on the dark header
PRIMARY = "#1F2A44"
PRIMARY_HOVER = "#2F3F66"
PRIMARY_OFF = "#A7AFBD"
FONT = "Segoe UI"

HOW_IT_WORKS = """\
What CrossArm does
CrossArm reads an ABB robot program (RAPID) and writes the equivalent FANUC programs (.LS). \
Motions, frames, I/O, registers and program logic are converted. What cannot be converted \
faithfully is never guessed: it is marked TODO in the program and listed in the report.

What you get, next to your ABB backup
  - one .LS program per RAPID routine, to load in ROBOGUIDE or on the controller;
  - crossarm_report.html: what was converted, what needs review, and the frames and I/O \
to set up on the robot;
  - SETUP_FRAMES.LS: sets the tool and user frames on the robot, run once before the \
programs instead of typing the values in (it starts with a pause, since it overwrites them);
  - crossarm_mapping.json: the frame, register and I/O numbers the programs use.

Getting the numbers right
The first run numbers everything from 1. To match your cell: give the backup of the FANUC \
robot in step 2 (its numbers already in use are left free), or edit crossarm_mapping.json, \
choose it in step 3 and convert again.

Moves inside routines
Many backups move through the integrator's own routines (a "MoveL" that also picks a station, \
checks a zone...). One that only moves is converted as the move. One that also does something \
else is your call: after a conversion, "choose which to convert" lists them with what they do \
besides; ticked ones are converted as the plain move, and that extra part is left out.

Before running a robot
The programs are a starting point for commissioning, not programs to run blind. Load them \
in ROBOGUIDE, work through every TODO in the report, and check reachability: another robot \
model may need another posture. The points are the ABB's, as theoretical points: touch them \
up on the robot. The path between them stays within 10 mm of the ABB's.

Your files
Everything runs on this computer: no file is sent anywhere. The output is written next to \
your input, in a new crossarm_<name> folder; a previous one is never overwritten.

Licence
Free for evaluation, development, teaching and personal use. Production use needs a \
commercial licence: enzoleroy56@gmail.com. Without one, every program CrossArm writes starts \
with "CrossArm EVALUATION copy". To install a licence file, click the licence status at the top \
right of the window.
CrossArm is independent and not affiliated with ABB or FANUC."""


def open_in_explorer(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def mapping_description(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    pinned = sum(len(v) for k, v in data.items() if isinstance(v, dict) and k not in ("limits", "reserved"))
    return f"{path.name}: {plural(pinned, 'number')} pinned."


class Step:
    """One numbered card: title, explanation, buttons, and a status line saying what was found."""

    def __init__(self, parent: tk.Widget, number: int, title: str, tag: str, explanation: str) -> None:
        self.frame = tk.Frame(parent, bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_EDGE)
        self.frame.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(self.frame, bg=CARD_BG)
        inner.pack(fill="x", padx=14, pady=12)

        head = tk.Frame(inner, bg=CARD_BG)
        head.pack(fill="x")
        badge = tk.Canvas(head, width=24, height=24, bg=CARD_BG, highlightthickness=0)
        badge.create_oval(1, 1, 23, 23, fill=PRIMARY, outline=PRIMARY)
        badge.create_text(12, 12, text=str(number), fill="white", font=(FONT, 10, "bold"))
        badge.pack(side="left")
        tk.Label(head, text=title, bg=CARD_BG, fg=TEXT, font=(FONT, 11, "bold")).pack(side="left", padx=(8, 6))
        tk.Label(head, text=tag, bg=CARD_BG, fg=MUTED, font=(FONT, 9)).pack(side="left")

        text = tk.Label(inner, text=explanation, bg=CARD_BG, fg=MUTED, font=(FONT, 9), justify="left", anchor="w")
        text.pack(fill="x", pady=(6, 8))
        self.buttons = tk.Frame(inner, bg=CARD_BG)
        self.buttons.pack(fill="x")
        self.status = tk.Label(inner, bg=CARD_BG, font=(FONT, 9), justify="left", anchor="w")
        self.status.pack(fill="x", pady=(8, 0))
        # Wrap text at the card's real width, which follows the window.
        inner.bind("<Configure>", lambda e: [w.config(wraplength=max(e.width - 8, 200)) for w in (text, self.status)])

    def button(self, text: str, command) -> ttk.Button:
        widget = ttk.Button(self.buttons, text=text, command=command, style="Card.TButton")
        widget.pack(side="left", padx=(0, 8))
        return widget

    def link(self, text: str, command) -> tk.Label:
        widget = tk.Label(self.buttons, text=text, bg=CARD_BG, fg=MUTED, font=(FONT, 9, "underline"), cursor="hand2")
        widget.bind("<Button-1>", lambda _: command())
        return widget

    def show(self, text: str, kind: str = "idle") -> None:
        mark, colour = {"idle": ("○", MUTED), "busy": ("…", MUTED), "ok": ("✔", OK), "fail": ("✖", FAIL)}[kind]
        self.status.config(text=f"{mark}  {text}", fg=colour)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"CrossArm {__version__}")
        self._icons = [tk.PhotoImage(data=ICON_PNG[s]) for s in (64, 32, 16)]  # kept alive
        self.iconphoto(True, *self._icons)
        scale = self.winfo_fpixels("1i") / 96  # 1.25 / 1.5 on scaled Windows displays
        self.geometry(f"{int(900 * scale)}x{int(640 * scale)}")
        self.minsize(int(820 * scale), int(600 * scale))
        self.configure(bg=BODY_BG)

        self.source: list[Path] | None = None  # RAPID inputs, FANUC ones set aside
        self.target: list[Path] | None = None  # the FANUC robot the programs will run on
        self.mapping: Path | None = None
        # Routines making a move and something else: convert their calls as the move? Ticked in the
        # window after a first conversion; overrides the mapping file for this input.
        self.move_choices: dict[str, bool] = {}
        self.last: pipeline.RunOutput | None = None
        self.busy = False
        self.convert_after_inspection = False
        self.log_lines: list[str] = []
        self.log_window: tk.Toplevel | None = None
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()

        self._styles()
        self._build()
        self._refresh()
        self.after(100, self._poll)

    # -- layout -----------------------------------------------------------

    def _styles(self) -> None:
        style = ttk.Style(self)
        style.configure("Card.TButton", background=CARD_BG, font=(FONT, 9))
        style.configure("TProgressbar", thickness=6)

    def _build(self) -> None:
        header = tk.Frame(self, bg=HEADER_BG)
        header.pack(fill="x")
        inner = tk.Frame(header, bg=HEADER_BG)
        inner.pack(fill="x", padx=18, pady=12)
        self._logo = tk.PhotoImage(data=ICON_PNG[32])
        tk.Label(inner, image=self._logo, bg=HEADER_BG).pack(side="left")
        tk.Label(inner, text="CrossArm", bg=HEADER_BG, fg="white", font=(FONT, 16, "bold")).pack(side="left", padx=(10, 8))
        tk.Label(inner, text="ABB RAPID  →  FANUC TP", bg=HEADER_BG, fg=HEADER_SUB, font=(FONT, 11)).pack(side="left")
        about = tk.Label(inner, text="How it works", bg=HEADER_BG, fg="white", font=(FONT, 10, "underline"),
                         cursor="hand2")  # fmt: skip
        about.pack(side="right")
        about.bind("<Button-1>", lambda _: self.show_help())
        self.licence: LicenceStatus = current_licence()
        self.licence_link = tk.Label(inner, bg=HEADER_BG, font=(FONT, 10, "underline"), cursor="hand2")
        self.licence_link.pack(side="right", padx=(0, 16))
        self.licence_link.bind("<Button-1>", lambda _: self.show_licence())
        self._show_licence_status()
        tk.Label(inner, text=f"v{__version__}", bg=HEADER_BG, fg=HEADER_SUB, font=(FONT, 9)).pack(side="right", padx=14)

        body = tk.Frame(self, bg=BODY_BG)
        body.pack(fill="both", expand=True, padx=18, pady=16)
        left = tk.Frame(body, bg=BODY_BG)
        left.pack(side="left", fill="both", expand=True)
        self.right = tk.Frame(body, bg=CARD_BG, highlightthickness=1, highlightbackground=CARD_EDGE, width=330)
        self.right.pack(side="right", fill="y", padx=(14, 0))
        self.right.pack_propagate(False)

        self.step_source = Step(
            left, 1, "ABB program to convert", "required",
            "A controller backup (folder or .zip) or RAPID modules. You can also drop them on the CrossArm.exe icon.",
        )  # fmt: skip
        self.inputs = [
            self.step_source.button("Backup folder...", self.pick_folder),
            self.step_source.button("Backup .zip...", self.pick_zip),
            self.step_source.button("RAPID files...", self.pick_files),
        ]
        self.step_target = Step(
            left, 2, "FANUC robot it will run on", "optional · recommended",
            "Its backup tells CrossArm which tool frames, registers and I/O are already used on the robot, "
            "so the converted programs leave them alone.",
        )  # fmt: skip
        self.inputs.append(self.step_target.button("FANUC backup folder...", self.pick_target))
        self.clear_target = self.step_target.link("Clear", self.forget_target)
        self.step_mapping = Step(
            left, 3, "Your numbering", "optional",
            "The crossarm_mapping.json written by a previous run, edited with your cell's numbers.",
        )  # fmt: skip
        self.inputs.append(self.step_mapping.button("Mapping file...", self.pick_mapping))
        self.clear_mapping = self.step_mapping.link("Clear", self.forget_mapping)

        action = tk.Frame(left, bg=BODY_BG)
        action.pack(fill="x", pady=(4, 0))
        self.convert_button = tk.Button(
            action, text="Convert", command=self.convert, font=(FONT, 11, "bold"), fg="white", bg=PRIMARY,
            activebackground=PRIMARY_HOVER, activeforeground="white", disabledforeground="white",
            relief="flat", padx=26, pady=7, cursor="hand2", borderwidth=0,
        )  # fmt: skip
        self.convert_button.pack(side="right")
        self.convert_button.bind("<Enter>", lambda _: self._hover(True))
        self.convert_button.bind("<Leave>", lambda _: self._hover(False))
        self.progress = ttk.Progressbar(action, mode="indeterminate", length=160)
        self.state_label = tk.Label(action, bg=BODY_BG, fg=MUTED, font=(FONT, 9), anchor="w")
        self.state_label.pack(side="left", fill="x", expand=True)

        self._show_what_you_get()

    def _panel(self) -> tk.Frame:
        """Empty the right-hand panel and return its content frame."""
        for child in self.right.winfo_children():
            child.destroy()
        inner = tk.Frame(self.right, bg=CARD_BG)
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        return inner

    def _text(self, parent: tk.Widget, text: str, *, size: int = 9, bold: bool = False, colour: str = TEXT,
              pad: tuple[int, int] = (0, 0)) -> tk.Label:  # fmt: skip
        label = tk.Label(parent, text=text, bg=CARD_BG, fg=colour, justify="left", anchor="w", wraplength=292,
                         font=(FONT, size, "bold" if bold else "normal"))  # fmt: skip
        label.pack(fill="x", pady=pad)
        return label

    def _show_what_you_get(self) -> None:
        panel = self._panel()
        self._text(panel, "What you will get", size=11, bold=True, pad=(0, 8))
        for title, text in (
            (".LS programs", "One FANUC program per RAPID routine, to load in ROBOGUIDE or on the controller."),
            ("Conversion report", "What was converted, what needs review, and the frames and I/O to set up."),
            ("SETUP_FRAMES.LS", "Sets the tool and user frames on the robot: run it once, nothing to type in."),
            ("crossarm_mapping.json", "The numbers the programs use. Edit it, choose it in step 3, convert again."),
        ):
            self._text(panel, title, bold=True, pad=(6, 0))
            self._text(panel, text, colour=MUTED)
        self._text(panel, "They are written next to your ABB backup. Nothing is sent anywhere.",
                   colour=MUTED, pad=(14, 0))  # fmt: skip
        self._text(panel, "The programs are a starting point for commissioning: check every TODO in the report "
                   "and touch up the points before running a robot.", colour=AMBER, pad=(10, 0))  # fmt: skip

    def _show_result(self, run: pipeline.RunOutput) -> None:
        summary = summarize(run)
        panel = self._panel()
        # The buttons first, at the bottom: with many lines to show, those lines are cut, not the buttons.
        buttons = tk.Frame(panel, bg=CARD_BG)
        buttons.pack(side="bottom", fill="x")
        look = {"font": (FONT, 10, "bold"), "fg": "white", "bg": PRIMARY, "activebackground": PRIMARY_HOVER,
                "activeforeground": "white", "relief": "flat", "padx": 14, "pady": 5, "cursor": "hand2",
                "borderwidth": 0}  # fmt: skip
        reports = [(t.task, t.report_html) for t in run.tasks if t.report_html]
        if len(reports) > 1:  # one report per robot task: let the user pick
            self.report_button: tk.Widget = tk.Menubutton(buttons, text="Open report ▾", **look)
            menu = tk.Menu(self.report_button, tearoff=False)
            for task, path in reports:
                menu.add_command(label=task, command=lambda p=path: open_in_explorer(p))
            self.report_button["menu"] = menu
        else:
            self.report_button = tk.Button(buttons, text="Open report", command=self.show_report, **look)
        self.report_button.pack(side="left")
        ttk.Button(buttons, text="Open folder", command=self.show_folder, style="Card.TButton").pack(side="left", padx=8)
        log = tk.Label(buttons, text="Log", bg=CARD_BG, fg=MUTED, font=(FONT, 9, "underline"), cursor="hand2")
        log.pack(side="right")
        log.bind("<Button-1>", lambda _: self.show_log())
        if move_decisions(run):
            choose = tk.Label(panel, text="Moves inside routines: choose which to convert...", bg=CARD_BG,
                              fg=PRIMARY, font=(FONT, 9, "underline"), cursor="hand2", anchor="w")  # fmt: skip
            choose.pack(side="bottom", fill="x", pady=(0, 8))
            choose.bind("<Button-1>", lambda _: self.choose_move_routines())
        self._text(panel, "Conversion done", size=11, bold=True)
        self._text(panel, f"Saved in {summary.folder.name}, next to your input.", colour=MUTED, pad=(0, 10))

        tiles = tk.Frame(panel, bg=CARD_BG)
        tiles.pack(fill="x", pady=(0, 10))
        tile_values: list[tuple[object, str, str]] = [
            (summary.programs, "programs", TEXT),
            (summary.ready, "ready as is", OK),
            (summary.to_review, "items to review", AMBER if summary.to_review else OK),
        ]
        if summary.converted is not None:
            tile_values.append((fmt_percent(summary.converted), "converted",
                                OK if summary.converted == 100 else TEXT))  # fmt: skip
        for value, caption, colour in tile_values:
            tile = tk.Frame(tiles, bg=BODY_BG)
            tile.pack(side="left", expand=True, fill="x", padx=(0, 6))
            tk.Label(tile, text=str(value), bg=BODY_BG, fg=colour, font=(FONT, 18, "bold")).pack(pady=(6, 0))
            tk.Label(tile, text=caption, bg=BODY_BG, fg=MUTED, font=(FONT, 8)).pack(pady=(0, 6))

        if summary.attention:
            self._text(panel, "What to look at", bold=True, pad=(0, 4))
            marks = {WARN: ("⚠", FAIL), INFO: ("•", TEXT), GOOD: ("✔", OK)}
            for level, line in summary.attention:
                row = tk.Frame(panel, bg=CARD_BG)
                row.pack(fill="x", pady=(0, 5))
                mark, colour = marks[level]
                tk.Label(row, text=mark, bg=CARD_BG, fg=colour, font=(FONT, 9, "bold"), width=2,
                         anchor="n").pack(side="left", anchor="n")  # fmt: skip
                tk.Label(row, text=line, bg=CARD_BG, fg=TEXT, font=(FONT, 9), justify="left", anchor="w",
                         wraplength=270).pack(side="left", fill="x")  # fmt: skip

    # -- state ----------------------------------------------------------------

    def _hover(self, inside: bool) -> None:
        if str(self.convert_button["state"]) != "disabled":
            self.convert_button.config(bg=PRIMARY_HOVER if inside else PRIMARY)

    def _refresh(self) -> None:
        """Enable what can be used now, and say what is missing."""
        ready = self.source is not None and not self.busy
        self.convert_button.config(state="normal" if ready else "disabled", bg=PRIMARY if ready else PRIMARY_OFF,
                                   text="Convert again" if self.last else "Convert")  # fmt: skip
        for widget in self.inputs:
            widget.config(state="disabled" if self.busy else "normal")
        for link, value in ((self.clear_target, self.target), (self.clear_mapping, self.mapping)):
            if value and not self.busy:
                link.pack(side="left", padx=(4, 0))
            else:
                link.pack_forget()
        if not self.busy:
            self.progress.stop()
            self.progress.pack_forget()
            if self.source is None:
                self.state_label.config(text="Start with step 1.")
            elif self.last is None:
                self.state_label.config(text="Ready to convert.")
        if self.source is None and not self.step_source.status.cget("text"):
            self.step_source.show("Nothing chosen yet.")
        if self.target is None:
            self.step_target.show("Not set: numbering starts at 1.")
        if self.mapping is None:
            self.step_mapping.show("Not set: numbers are allocated automatically.")

    def _set_busy(self, text: str) -> None:
        self.busy = True
        self.state_label.config(text=text)
        self.progress.pack(side="left", padx=(0, 10), before=self.state_label)
        self.progress.start(12)
        self._refresh()

    def _set_idle(self, text: str = "") -> None:
        self.busy = False
        self._refresh()
        if text:
            self.state_label.config(text=text)

    # -- step 1: ABB input ------------------------------------------------------

    def pick_folder(self) -> None:
        folder = filedialog.askdirectory(title="ABB backup folder")
        if folder:
            self.choose_source([Path(folder)])

    def pick_zip(self) -> None:
        archive = filedialog.askopenfilename(title="Zipped ABB backup", filetypes=[("Zip archive", "*.zip")])
        if archive:
            self.choose_source([Path(archive)])

    def pick_files(self) -> None:
        files = filedialog.askopenfilenames(
            title="RAPID modules", filetypes=[("RAPID modules", RAPID_PATTERNS), ("All files", "*.*")]
        )
        if files:
            self.choose_source([Path(f) for f in files])

    def choose_source(self, paths: list[Path], convert: bool = False) -> None:
        """Inspect the input and say what it holds; convert afterwards when asked (icon drop)."""
        self.convert_after_inspection = convert
        self.step_source.show("Reading...", "busy")
        self._set_busy("Reading the ABB input...")
        self._run(lambda: ("inspected", (paths, pipeline.inspect(paths))), "source")

    def _inspected(self, paths: list[Path], info: pipeline.Inspection) -> None:
        self.source = [p for p in paths if p not in info.fanuc]
        self.move_choices = {}  # they were about the previous input's routines
        if self.last is not None:  # a new input: the previous result no longer applies
            self.last = None
            self._show_what_you_get()
        self.step_source.show(describe_source(info), "ok")
        if info.fanuc:  # FANUC backup dropped together with the ABB one
            self._set_target(info.fanuc)
            return
        self._set_idle()
        self._maybe_convert()

    def _maybe_convert(self) -> None:
        if self.convert_after_inspection:
            self.convert_after_inspection = False
            self.convert()

    # -- step 2: target FANUC robot --------------------------------------------

    def pick_target(self) -> None:
        folder = filedialog.askdirectory(title="Backup of the FANUC robot (.LS programs)")
        if not folder:
            return
        if not is_fanuc_input(Path(folder)):
            self.step_target.show("No FANUC .LS program in this folder, or it also holds RAPID modules.", "fail")
            return
        self._set_target([Path(folder)])

    def _set_target(self, paths: list[Path]) -> None:
        self.step_target.show("Reading...", "busy")
        self._set_busy("Reading the FANUC programs...")
        self._run(lambda: ("controller", (paths, read_controller(paths))), "target")

    def _controller_read(self, paths: list[Path], usage) -> None:
        self.target = paths
        self.step_target.show(f"{', '.join(p.name for p in paths)}: {describe_controller(usage)}", "ok")
        self._set_idle()
        self._maybe_convert()

    def forget_target(self) -> None:
        self.target = None
        self._refresh()

    # -- step 3: mapping file ------------------------------------------------------

    def pick_mapping(self) -> None:
        path = filedialog.askopenfilename(title="Mapping file", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            ConversionConfig.from_mapping_file(path)
            text = mapping_description(Path(path))
        except (OSError, ValueError, TypeError) as exc:
            self.step_mapping.show(f"Not usable: {exc}", "fail")
            return
        self.mapping = Path(path)
        self.step_mapping.show(text, "ok")
        self._refresh()

    def forget_mapping(self) -> None:
        self.mapping = None
        self._refresh()

    # -- conversion (background thread) -------------------------------------------

    def convert(self) -> None:
        if self.source is None or self.busy:
            return
        self.log_lines.clear()
        self._set_busy("Converting...")
        source, target, mapping = self.source, self.target, self.mapping
        choices = dict(self.move_choices)

        def log(line: str) -> None:
            self.messages.put(("log", line))

        def work():
            config = ConversionConfig.from_mapping_file(mapping) if mapping else ConversionConfig()
            config.move_routines.update(choices)
            return "done", pipeline.run(source, config=config, log=log, fanuc=list(target) if target else None)

        self._run(work, "convert")

    def _run(self, job, stage: str) -> None:
        context = {"stage": stage, "input": self.source, "target": self.target, "mapping": self.mapping}

        def worker():
            try:
                self.messages.put(job())
            except (OSError, ValueError, TypeError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
                self.messages.put(("error", (stage, str(exc))))
            except Exception as exc:  # noqa: BLE001 - never leave the window stuck on "busy"
                # A bug: keep the traceback the message box cannot show, and say where it is.
                try:
                    where = f" Details saved in {write_error_report(exc, context)}: please send that file."
                except OSError:
                    where = ""
                self.messages.put(("error", (stage, f"unexpected error ({type(exc).__name__}): {exc}.{where}")))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self) -> None:
        while not self.messages.empty():
            kind, payload = self.messages.get()
            if kind == "log":
                self._log(str(payload))
            elif kind == "inspected":
                self._inspected(*payload)  # type: ignore[misc]
            elif kind == "controller":
                self._controller_read(*payload)  # type: ignore[misc]
            elif kind == "done":
                self._finished(payload)  # type: ignore[arg-type]
            elif kind == "error":
                self._failed(*payload)  # type: ignore[misc]
        self.after(100, self._poll)

    def _finished(self, run: pipeline.RunOutput) -> None:
        self.last = run
        self._set_idle(f"Done: {plural(run.programs, 'program')} written.")
        self._show_result(run)

    def _failed(self, stage: str, message: str) -> None:
        self.convert_after_inspection = False
        step = {"source": self.step_source, "target": self.step_target}.get(stage)
        if stage == "source":
            self.source = None
        if step:
            step.show(message[:1].upper() + message[1:], "fail")
            self._set_idle()
        else:
            self._log(f"ERROR: {message}")
            self._set_idle("Conversion failed: see the log.")
            messagebox.showerror("CrossArm", f"The conversion failed:\n\n{message}")

    # -- output ---------------------------------------------------------------

    def _log(self, line: str) -> None:
        self.log_lines.append(line)
        if not line.startswith(" "):
            self.state_label.config(text=line[:90])
        if self.log_window is not None and self.log_window.winfo_exists():
            view = self.log_window.view  # type: ignore[attr-defined]
            view.config(state="normal")
            view.insert("end", line + "\n")
            view.see("end")
            view.config(state="disabled")

    def choose_move_routines(self) -> None:
        """Which routines that make a move and do something else are converted as that move.

        The choice cannot be made for the user: converting such a call as the plain move drops
        what the routine does around it, e.g. choosing the point from a parameter.
        So the dialog says what each one does besides, and converts again with the choice.
        """
        if self.last is None or self.busy:
            return
        decisions = move_decisions(self.last)
        dialog = tk.Toplevel(self, bg=CARD_BG)
        dialog.title("Moves inside routines")
        dialog.transient(self)
        body = tk.Frame(dialog, bg=CARD_BG)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        def text(parent: tk.Widget, value: str, fg: str = TEXT, font: tuple = (FONT, 9), padx=0, pady=0) -> None:
            tk.Label(parent, text=value, bg=CARD_BG, fg=fg, justify="left", anchor="w", wraplength=520,
                     font=font).pack(fill="x", padx=padx, pady=pady)  # fmt: skip

        text(body, "Moves made inside routines", font=(FONT, 11, "bold"))
        text(body, (
            "These routines of the backup take a point, a speed, a zone and a tool and make one move with them, "
            "but they also do something else. Converted as the plain move, that part is left out: the robot "
            "goes to the point as written, whatever the routine would have changed. Tick a routine only if "
            "that is right for the new cell."
        ), fg=MUTED, pady=(4, 10))  # fmt: skip
        ticks: dict[str, tk.BooleanVar] = {}
        for key, name, instruction, calls, also, converted in decisions:
            ticks[key] = tk.BooleanVar(dialog, value=converted)
            tk.Checkbutton(body, text=f"{name}  →  {instruction}    ({plural(calls, 'move')})", variable=ticks[key],
                           bg=CARD_BG, activebackground=CARD_BG, font=(FONT, 9, "bold"),
                           anchor="w").pack(fill="x")  # fmt: skip
            text(body, f"Also: {also}", fg=MUTED, padx=24, pady=(0, 6))
        buttons = tk.Frame(body, bg=CARD_BG)
        buttons.pack(fill="x", pady=(8, 0))

        def apply() -> None:
            self.move_choices.update({name: var.get() for name, var in ticks.items()})
            dialog.destroy()
            self.convert()

        tk.Button(buttons, text="Convert again", command=apply, font=(FONT, 10, "bold"), fg="white", bg=PRIMARY,
                  activebackground=PRIMARY_HOVER, activeforeground="white", relief="flat", padx=14, pady=5,
                  cursor="hand2", borderwidth=0).pack(side="right")  # fmt: skip
        ttk.Button(buttons, text="Cancel", command=dialog.destroy, style="Card.TButton").pack(side="right", padx=8)
        self.move_dialog = dialog

    def show_log(self) -> None:
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.lift()
            return
        window = tk.Toplevel(self)
        window.title("CrossArm - conversion log")
        window.geometry(f"{int(720 * self.winfo_fpixels('1i') / 96)}x{int(360 * self.winfo_fpixels('1i') / 96)}")
        view = ScrolledText(window, font=("Consolas", 9), state="normal", wrap="none")
        view.pack(fill="both", expand=True)
        view.insert("end", "\n".join(self.log_lines) + "\n")
        view.config(state="disabled")
        window.view = view  # type: ignore[attr-defined]
        self.log_window = window

    def _show_licence_status(self) -> None:
        if self.licence.licensed:
            self.licence_link.config(text="Licensed", fg=HEADER_SUB)
        else:
            self.licence_link.config(text="Evaluation copy", fg=EVALUATION)

    def show_licence(self) -> None:
        """Who CrossArm is licensed to, and a way to install a licence file without looking for a folder."""
        dialog = tk.Toplevel(self, bg=CARD_BG)
        dialog.title("Licence")
        dialog.transient(self)
        body = tk.Frame(dialog, bg=CARD_BG)
        body.pack(fill="both", expand=True, padx=18, pady=14)
        status = tk.Label(body, bg=CARD_BG, justify="left", anchor="w", wraplength=460, font=(FONT, 10, "bold"))
        status.pack(fill="x")
        detail = tk.Label(body, bg=CARD_BG, fg=MUTED, justify="left", anchor="w", wraplength=460, font=(FONT, 9))
        detail.pack(fill="x", pady=(6, 12))

        def refresh(message: str = "", failed: bool = False) -> None:
            status.config(text=self.licence.describe(), fg=OK if self.licence.licensed else TEXT)
            text = message or (
                f"Licence file: {self.licence.path}" if self.licence.licensed else
                "CrossArm is free to evaluate, develop with, teach and learn. Using its programs in production —"
                " on a robot doing real work, or delivered to a customer — needs a commercial licence. Without"
                " one, every program it writes starts with \"CrossArm EVALUATION copy\"."
            )  # fmt: skip
            detail.config(text=text, fg=FAIL if failed else MUTED)

        def install() -> None:
            chosen = filedialog.askopenfilename(parent=dialog, title="crossarm licence file",
                                                filetypes=[("crossarm licence", "*.licence"), ("All files", "*.*")])  # fmt: skip
            if not chosen:
                return
            found = read_licence(Path(chosen))
            if not found.licensed:
                refresh(f"Not installed: {found.reason}.", failed=True)
                return
            target = licence_folder() / LICENCE_FILE
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(Path(chosen).read_bytes())
            except OSError as exc:
                refresh(f"Not installed: {exc}", failed=True)
                return
            self.licence = current_licence()
            self._show_licence_status()
            refresh(f"Installed in {target}. Programs converted from now on carry the licence.")

        buttons = tk.Frame(body, bg=CARD_BG)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Install a licence file...", command=install, style="Card.TButton").pack(side="left")
        ttk.Button(buttons, text="Close", command=dialog.destroy, style="Card.TButton").pack(side="right")
        refresh()
        self.licence_dialog = dialog

    def show_help(self) -> None:
        window = tk.Toplevel(self, bg=CARD_BG)
        window.title("How CrossArm works")
        window.transient(self)
        text = tk.Text(window, wrap="word", bg=CARD_BG, fg=TEXT, font=(FONT, 10), relief="flat", padx=20,
                       pady=16, width=78, height=30, borderwidth=0)  # fmt: skip
        text.tag_configure("title", font=(FONT, 11, "bold"), spacing1=10, spacing3=4)
        for paragraph in HOW_IT_WORKS.split("\n\n"):
            title, _, body = paragraph.partition("\n")
            text.insert("end", title + "\n", "title")
            text.insert("end", body + "\n")
        text.config(state="disabled")
        text.pack(fill="both", expand=True)
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=(0, 14))

    def show_folder(self) -> None:
        if self.last:
            open_in_explorer(self.last.folder)

    def show_report(self) -> None:
        report = summarize(self.last).report if self.last else None
        if report:
            open_in_explorer(report)


def move_decisions(run: pipeline.RunOutput) -> list[tuple[str, str, str, int, str, bool]]:
    """(upper-case key, name, instruction, calls, what else it does, converted) for every routine of this run
    that makes a move and something else: the ones the user decides on."""
    found: dict[str, list] = {}
    for task in run.tasks:
        for use in task.result.move_routines if task.result else []:
            if use.pure:
                continue
            key = use.name.upper()
            if key in found:
                found[key][2] += use.calls
            else:
                found[key] = [use.name, use.instruction, use.calls, use.also_does, use.converted]
    return [(key, *found[key]) for key in sorted(found, key=lambda k: -found[k][2])]  # type: ignore[misc]


def _sharp_on_high_dpi() -> None:
    """Without this, Windows scales the window as a bitmap on 125-150 % displays: blurry text."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            # Own taskbar entry and icon, instead of being grouped under python.exe.
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("crossarm.desktop")
        except (AttributeError, OSError):
            pass


def close_splash() -> None:
    """CrossArm.exe shows a splash image the moment it is launched, while it unpacks (2 to 3 s
    with nothing on screen otherwise, and users launch it again). Close it once the window
    is up. pyi_splash only exists in an executable built with PyInstaller --splash."""
    try:
        import pyi_splash  # type: ignore[import-not-found]
    except ImportError:
        return
    pyi_splash.close()


def launch(paths: list[Path] | None = None) -> None:
    _sharp_on_high_dpi()
    app = App()
    app.update_idletasks()
    app.after(0, close_splash)  # the window is drawn: the splash can go
    if paths:
        app.after(200, app.choose_source, paths, True)  # dropped on the exe icon: convert right away
    app.mainloop()
