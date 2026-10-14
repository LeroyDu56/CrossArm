# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID's instructions for several tasks or robots working together (Multitasking, MultiMove options): what each is
for, and why it stays TODO, rather than "call to WaitSyncTask with arguments has no mapping".

CrossArm converts each RAPID task into programs of their own. What makes the tasks meet, share a semaphore or move
their robots together has no TP instruction: the FANUC cell does it another way, set up by hand (flags or outputs
each program sets and waits for, the controller's coordinated motion options). Nothing here is converted; no TP form
is written without being measured first.
"""

from collections.abc import Iterable

from crossarm.convert.blockers import Blocker
from crossarm.rapid import nodes as n

COORDINATED = ("coordinated motion of several robots (MultiMove option, SyncMoveOn ... SyncMoveOff): TP has no"
               " instruction for it; the FANUC coordinates motion groups with its own options, set up on the"
               " controller. Each robot's moves are converted alone, not coordinated")  # fmt: skip
MEETING = ("a meeting point of RAPID tasks (Multitasking option): TP has no instruction for one; on the FANUC each"
           " program sets a flag or an output when it gets there and waits for the others' (WAIT), set up by hand")  # fmt: skip
SEMAPHORE = ("a semaphore shared by RAPID tasks: TP has no test-and-set in one step (two programs may both find a flag"
             " free); a handshake by flags or outputs is set up by hand")  # fmt: skip

# upper-case RAPID name -> (why, cause)
MULTITASK = {
    **{name: (COORDINATED, Blocker.MOTION) for name in (
        "SYNCMOVEON", "SYNCMOVEOFF", "SYNCMOVERESUME", "SYNCMOVESUSPEND", "SYNCMOVEUNDO")},
    "WAITSYNCTASK": (MEETING, Blocker.NO_TP_EQUIVALENT),
    "WAITTESTANDSET": (SEMAPHORE, Blocker.NO_TP_EQUIVALENT),
}  # fmt: skip


def multitask_todo(stmt: n.Stmt, routines: Iterable[str]) -> tuple[str, str] | None:
    """(why, cause) when the statement is one of RAPID's instructions for tasks or robots working together; None
    otherwise. The backup's own routines of the same name are not RAPID's. Their functions (IsSyncMoveOn,
    TestAndSet) are in conditions, written with their blocks (convert.condition_gates)."""
    if not isinstance(stmt, n.ProcCall):
        return None
    found = MULTITASK.get(stmt.name.upper())
    if found is None or stmt.name.upper() in {name.upper() for name in routines}:
        return None
    return f"{stmt.name}: {found[0]}", found[1]
