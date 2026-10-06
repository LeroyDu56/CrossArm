# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The desktop window, driven through its states.

What the window says is tested without a display in test_summary_text.py; this drives
the window itself — steps, conversion, result panel, errors — where a display exists
(Windows CI, a developer machine). A name clash that would have crashed the result
panel on its first warning was found by reading the code: these tests would have
caught it. Skipped where Tk cannot open a window.
"""

import gc
import os
import shutil
import time
import tkinter as tk
from pathlib import Path

import pytest
from test_backup import make_backup
from test_summary_text import tool_rack


@pytest.fixture(scope="module")
def window():
    """One window for the module, as the application has one per process. Creating and
    destroying a Tcl interpreter per test fails now and then on Windows ("invalid command
    name tcl_findLibrary"), which would make these tests flaky for no fault of crossarm."""
    from crossarm import gui

    try:
        app = gui.App()
    except tk.TclError as exc:
        if os.environ.get("CROSSARM_REQUIRE_GUI") == "1":  # set on Windows CI: skipping there would hide a gap
            raise
        pytest.skip(f"no display for Tk: {exc}")
    app.withdraw()
    yield app
    # Free the Tk images on the main thread: left to the garbage collector, they may be
    # deleted later from a worker thread, which Tk refuses.
    app._icons, app._logo = [], None
    gc.collect()
    app.destroy()


@pytest.fixture
def app(window, monkeypatch):
    """The window as it is when it has just opened."""
    from crossarm import gui

    errors: list[str] = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda _title, message: errors.append(message))
    while not window.messages.empty():
        window.messages.get()
    for child in window.winfo_children():
        if isinstance(child, tk.Toplevel):
            child.destroy()
    window.source = window.target = window.mapping = window.last = window.log_window = window.tp_robot = None
    window.move_choices = {}
    window.busy = window.convert_after_inspection = False
    window.step_source.status.config(text="")
    window._show_what_you_get()
    window._refresh()
    window.errors = errors  # type: ignore[attr-defined]
    return window


def settle(app, timeout: float = 30) -> None:
    """Let the background thread finish and the window process its messages."""
    end = time.time() + timeout
    while time.time() < end:
        app.update()
        if not app.busy and app.messages.empty():
            break
        time.sleep(0.02)
    for _ in range(3):
        app.update()
    assert not app.busy, "the window is still busy"


def texts(widget: tk.Misc) -> list[str]:
    found = []
    for child in widget.winfo_children():
        if "text" in child.keys() and child.cget("text"):  # noqa: SIM118 - a Tk widget, not a dict
            found.append(str(child.cget("text")))
        found += texts(child)
    return found


@pytest.fixture
def fanuc_robot(tmp_path, fixtures_dir):
    folder = tmp_path / "fanuc_robot"
    shutil.copytree(fixtures_dir / "fanuc" / "roboguide_export", folder)
    return folder


@pytest.fixture
def module(tmp_path, fixtures_dir):
    path = tmp_path / "pick_and_place.mod"
    path.write_bytes((fixtures_dir / "rapid" / "pick_and_place.mod").read_bytes())
    return path


def test_nothing_can_start_before_step_1(app):
    assert str(app.convert_button["state"]) == "disabled"
    assert "○  Nothing chosen yet." in app.step_source.status.cget("text")
    assert "What you will get" in texts(app.right)


def test_choosing_the_abb_input_says_what_was_found_and_enables_convert(app, module):
    app.choose_source([module])
    settle(app)
    assert app.step_source.status.cget("text").startswith("✔  1 RAPID module (pick_and_place).")
    assert str(app.convert_button["state"]) == "normal"
    assert app.last is None  # nothing converted yet


def test_convert_shows_the_result_in_plain_words(app, module, fanuc_robot):
    app.choose_source([module])
    settle(app)
    app._set_target([fanuc_robot])
    settle(app)
    assert app.step_target.status.cget("text").startswith("✔  fanuc_robot: 6 programs read.")
    app.convert()
    settle(app)
    shown = texts(app.right)
    assert "Conversion done" in shown and "Saved in crossarm_pick_and_place, next to your input." in shown
    assert ["3", "2", "3"] == [t for t in shown if t.isdigit()]  # programs, ready as is, items to review
    assert any(t.startswith("Numbers already used on the FANUC robot were left free") for t in shown)
    assert app.convert_button.cget("text") == "Convert again"


def test_warnings_are_drawn_without_error(app, tmp_path):
    """The result path that a name clash (a colour called WARN) would have crashed."""
    app.choose_source([tool_rack(tmp_path, 12, broken=True)])
    settle(app)
    app.convert()
    settle(app)
    shown = texts(app.right)
    assert "⚠" in shown
    assert any(t.startswith("Set the payload of 12 tools") for t in shown)


def test_moves_inside_routines_are_chosen_in_the_window(app, tmp_path):
    """Ticking a routine converts its calls as moves, without editing the mapping file by hand."""
    source = tmp_path / "cell.mod"
    source.write_text("\n".join([
        "MODULE M",
        "CONST robtarget pHome:=[[600,0,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];",
        "VAR bool bSideB;",
        "PROC main()", *["  MoveLSide pHome,v500,z10,tool0;"] * 3, "ENDPROC",
        "PROC MoveLSide(robtarget ToPoint,speeddata Speed,zonedata Zone,PERS tooldata Tool,\\PERS wobjdata WObj)",
        "  VAR robtarget Target;", "  Target:=ToPoint;",
        "  IF bSideB Target:=Flip(ToPoint);",
        "  MoveL Target,Speed,Zone,Tool\\WObj?WObj;",
        "ENDPROC", "ENDMODULE", "",
    ]), encoding="utf-8")  # fmt: skip
    app.choose_source([source])
    settle(app)
    app.convert()
    settle(app)
    assert app.last.todo == 3
    assert "Moves inside routines: choose which to convert..." in texts(app.right)
    app.choose_move_routines()
    app.update()
    shown = texts(app.move_dialog)
    assert "MoveLSide  →  MoveL    (3 moves)" in shown
    assert any(t.startswith("Also: changes the point: Target:=Flip(ToPoint)") for t in shown)
    checkbox = next(w for w in app.move_dialog.winfo_children()[0].winfo_children() if isinstance(w, tk.Checkbutton))
    checkbox.invoke()
    next(w for w in texts_widgets(app.move_dialog) if w.cget("text") == "Convert again").invoke()
    settle(app)
    assert app.move_choices == {"MOVELSIDE": True}
    assert app.last.todo == 0
    # The choice is kept in the mapping file written with the result, for the next run.
    mapping = app.last.folder / "crossarm_mapping.json"
    assert '"MoveLSide": true' in mapping.read_text(encoding="utf-8")


def texts_widgets(widget: tk.Misc) -> list[tk.Misc]:
    found = []
    for child in widget.winfo_children():
        if "text" in child.keys():  # noqa: SIM118 - a Tk widget, not a dict
            found.append(child)
        found += texts_widgets(child)
    return found


def test_a_backup_with_several_tasks_offers_each_report(app, tmp_path):
    app.choose_source([make_backup(tmp_path / "Cell")])
    settle(app)
    app.convert()
    settle(app)
    button = app.report_button
    assert isinstance(button, tk.Menubutton) and button.cget("text") == "Open report ▾"
    menu = app.nametowidget(button["menu"])
    assert [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)] == ["T_ROB1", "T_ROB2"]


def test_an_input_without_rapid_is_refused_on_its_step(app, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    app.choose_source([empty])
    settle(app)
    assert app.step_source.status.cget("text").startswith("✖  No RAPID module found")
    assert str(app.convert_button["state"]) == "disabled"


def test_both_backups_dropped_on_the_icon_are_converted_straight_away(app, module, fanuc_robot):
    app.choose_source([module, fanuc_robot], True)
    settle(app)
    assert app.target == [fanuc_robot]
    assert app.last is not None and app.last.controller is not None


def test_an_unexpected_error_keeps_its_traceback_and_says_where(app, module, monkeypatch, tmp_path):
    from crossarm import pipeline

    def boom(*args, **kwargs):
        raise RuntimeError("simulated bug")

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    app.choose_source([module])
    settle(app)
    monkeypatch.setattr(pipeline, "run", boom)
    app.convert()
    settle(app)
    [message] = app.errors
    report = tmp_path / "appdata" / "CrossArm" / "crossarm_error.txt"
    assert "unexpected error (RuntimeError): simulated bug" in message
    assert str(report) in message
    assert "RuntimeError: simulated bug" in report.read_text(encoding="utf-8")


def test_log_and_help_windows_open(app, module):
    app.choose_source([module])
    settle(app)
    app.convert()
    settle(app)
    app.show_log()
    app.show_help()
    app.update()
    titles = [w.title() for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
    assert titles == ["CrossArm - conversion log", "How CrossArm works"]
    assert "RAPID files 'pick_and_place': 1 task(s)" in app.log_window.view.get("1.0", "end")  # type: ignore[union-attr]


def test_the_output_folder_is_written_next_to_the_input(app, module):
    app.choose_source([module])
    settle(app)
    app.convert()
    settle(app)
    folder = Path(app.last.folder)
    assert folder.parent == module.parent
    assert (folder / "crossarm_log.txt").exists()


def test_a_licence_file_is_installed_from_the_window(app, tmp_path, monkeypatch):
    from datetime import date

    from crossarm import gui
    from crossarm import licence as lic

    secret = bytes(range(32))  # test key: licences signed with it are only valid while patched in
    monkeypatch.setattr(lic, "PUBLIC_KEY", lic.public_key(secret))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.delenv("CROSSARM_LICENCE", raising=False)
    app.licence = lic.current()
    app._show_licence_status()
    assert app.licence_link.cget("text") == "Evaluation copy"
    source = tmp_path / "crossarm.licence"
    source.write_text(lic.issue(secret, "ACME Robotics", "RC-1", date(2099, 1, 1)), encoding="utf-8")
    monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **_: str(source))
    app.show_licence()
    app.update()
    assert "Evaluation copy" in texts(app.licence_dialog)[0]
    next(w for w in texts_widgets(app.licence_dialog) if w.cget("text") == "Install a licence file...").invoke()
    app.update()
    assert app.licence_link.cget("text") == "Licensed"
    assert (tmp_path / "appdata" / "CrossArm" / "crossarm.licence").is_file()
    assert any(t.startswith("Installed in") for t in texts(app.licence_dialog))
    app.licence = lic.LicenceStatus(None)  # the window is shared by the module's tests
    app._show_licence_status()


def test_the_tp_step_says_at_once_when_maketp_or_the_robot_is_missing(app, tmp_path, monkeypatch):
    from crossarm import gui
    from crossarm.fanuc import maketp

    assert app.step_tp.status.cget("text") == "○  Not set: only .LS programs are written."
    monkeypatch.setattr(gui, "find_maketp", lambda: None)
    app.set_tp_robot(tmp_path)
    assert app.tp_robot is None and app.step_tp.status.cget("text").startswith("✖  Not usable: FANUC MakeTP not found")
    monkeypatch.setattr(gui, "find_maketp", lambda: tmp_path / "maketp.exe")
    app.set_tp_robot(tmp_path)
    assert app.tp_robot is None and "nor a robot.ini" in app.step_tp.status.cget("text")
    (tmp_path / "Robot_1").mkdir()
    (tmp_path / "Robot_1" / "frvirt.dat").write_text("V10.10270\n", encoding="ascii")
    app.set_tp_robot(tmp_path / "Robot_1")
    assert app.tp_robot == tmp_path / "Robot_1" and app.step_tp.status.cget("text").startswith("✔  Robot_1: .TP files")
    assert maketp.check_robot(tmp_path) == ""
    app.forget_tp_robot()
    assert app.tp_robot is None
