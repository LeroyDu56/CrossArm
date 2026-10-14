# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Load / StartLoad / WaitLoad / UnLoad / EraseModule of a module the backup holds: a remark and a warning (its
programs are on the controller with the others); of a module it does not hold, or named at run time: TODO saying so.
GetSysData of a tool or work object selected before it in the routine: copied from it; else TODO (VARS-034)."""

from test_translate import HOME, TOOL, WOBJ, run, todos, tp_lines

from crossarm.convert import triage
from crossarm.convert.analysis import priority_actions
from crossarm.convert.blockers import Blocker
from crossarm.convert.module_loads import module_of
from crossarm.diagnose import loaded_modules

SESSION = "VAR loadsession lsNext;"
CUR = "PERS tooldata tCur:=[TRUE,[[0,0,100],[1,0,0,0]],[2.4,[0,0,90],[1,0,0,0],0,0,0]];"
WCUR = 'PERS wobjdata wCur:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];'
LOAD = "PERS loaddata loBox:=[1.5,[0,0,20],[1,0,0,0],0,0,0];"


def test_module_of_a_file_path():
    assert module_of("HOME:/Parts/PartA.modx") == "PARTA"
    assert module_of("HOME:Station2.MOD") == "STATION2"
    assert module_of("diskhome\\Cell.sys") == "CELL"


def test_a_module_of_the_backup_is_a_remark_and_a_warning():
    body = ('Load \\Dynamic, "HOME:/M.mod";\nStartLoad \\Dynamic, "HOME:" \\File:="m.modx", lsNext;\n'
            'WaitLoad lsNext;\nUnLoad "HOME:/M.mod";\nEraseModule "M";')  # fmt: skip
    result = run(body, SESSION)
    assert not todos(result)
    assert tp_lines(result) == ["!l.4 Load M (loaded)", "!l.5 StartLoad M (loaded)", "!l.6 WaitLoad M (loaded)",
                                "!l.7 UnLoad M (kept)", "!l.8 EraseModule M (kept)"]  # fmt: skip
    warnings = [n.message for n in result.notes if n.kind == "WARNING"]
    assert len(warnings) == 5 and all("has no modules" in w for w in warnings)


def test_a_module_not_in_the_backup_is_todo_saying_so():
    body = 'Load \\Dynamic, "HOME:/Other.mod";\nUnLoad "HOME:" \\File:="Other.mod";\nLoad sPath;\nWaitLoad lsNext;'
    result = run(body, SESSION + 'VAR string sPath:="";\nPROC set()\nsPath:="HOME:/A.mod";\nENDPROC')
    other, unload, named, waited = todos(result)
    assert "module OTHER is not in the input: add its file" in other and "module OTHER" in unload
    assert "named at run time" in named
    assert "no StartLoad" in waited
    causes = [note.category for note in result.notes if note.kind == "TODO"]
    assert causes == [Blocker.LOADED_MODULE] * 3 + [Blocker.MISSING]
    # Kept for the analysis: the file as the RAPID names it, one entry per line left TODO.
    assert [(m.module, m.path, m.line) for m in result.loaded_missing] == [
        ("OTHER", "HOME:/Other.mod", 7), ("OTHER", "HOME:/Other.mod", 8), ("", "", 9)]


def test_the_analysis_asks_for_the_module_files_to_add_and_the_diagnostic_counts_them():
    body = ('Load \\Dynamic, "HOME:/jobs/JobsB.mod";\nStartLoad \\Dynamic, "HOME:/jobs" \\File:="JobsC.modx", lsNext;\n'
            'WaitLoad lsNext;\nUnLoad "HOME:/jobs/JobsB.mod";\nLoad sPath;')  # fmt: skip
    result = run(body, SESSION + 'VAR string sPath:="";\nPROC set()\nsPath:="HOME:/A.mod";\nENDPROC')
    action = next(a for a in priority_actions(result) if a.causes == (Blocker.LOADED_MODULE,))
    assert action.title == "Add the 2 module files the programs load to the input"
    assert "`HOME:/jobs/JobsB.mod`, `HOME:/jobs/JobsC.modx`" in action.detail
    assert "1 load names its file at run time" in action.detail
    assert action.todo == 5 and action.who == (triage.BACKUP,)
    assert loaded_modules(result) == {"loaded_modules_missing": 2, "loaded_modules_named_at_run_time": 1}


def test_save_stays_without_a_tp_equivalent():
    (save,) = todos(run('Save "M" \\FilePath:="HOME:/M.mod";'))
    assert "TP has none" in save


def test_get_sys_data_copies_the_frame_selected_before_it():
    body = "MoveL pHome,v100,fine,tGrip\\WObj:=wFix;\nGetSysData tCur;\nGetSysData wCur;\nMoveL pHome,v100,fine,tCur\\WObj:=wCur;"
    result = run(body, HOME + TOOL + WOBJ + CUR + WCUR)
    assert not todos(result)
    lines = tp_lines(result)
    assert lines[3:7] == ["!l.5 GetSysData tCur", "UTOOL[2]=PR[99]", "!l.6 GetSysData wCur", "UFRAME[2]=PR[98]"]
    assert lines[7:9] == ["UFRAME_NUM=2", "UTOOL_NUM=2"]
    copy = tp_lines(run(body.replace("GetSysData tCur;", "tCur := tGrip;").replace("GetSysData wCur;", "wCur := wFix;"),
                        HOME + TOOL + WOBJ + CUR + WCUR))  # fmt: skip
    assert [x for x in lines if not x.startswith("!")] == [x for x in copy if not x.startswith("!")]


def test_get_sys_data_of_the_active_frame_itself_is_a_remark():
    result = run("MoveL pHome,v100,fine,tGrip;\nGetSysData tGrip;\nMoveL pHome,v100,fine,tGrip;", HOME + TOOL)
    assert not todos(result)
    assert tp_lines(result)[3:] == ["!l.5 GetSysData tGrip", "L P[1] 100mm/sec FINE"]


def test_get_sys_data_not_known_here_stays_todo():
    # at the start of the routine, or after a call: the frame is the one the caller selected
    result = run("GetSysData tCur;\nMoveL pHome,v100,fine,tGrip;\nsub;\nGetSysData tCur;", HOME + TOOL + CUR,
                 extra_procs="PROC sub()\nENDPROC")  # fmt: skip
    first, second = todos(result)
    assert "VARS-034" in first and "VARS-034" in second


def test_get_sys_data_of_a_load_keeps_the_payload():
    result = run("GetSysData loBox;", LOAD)
    assert not todos(result) and tp_lines(result) == ["!l.4 GetSysData loBox"]
    assert any("PAYLOAD schedule" in n.message for n in result.notes if n.kind == "WARNING")
