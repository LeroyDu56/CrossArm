# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A stationary tool and a robot-held work object: the FANUC Remote TCP (a mixin of the routine translator).

The robot carries the part to a tool fixed in the cell (a glue nozzle, a deburring spindle, a pedestal gun):

    MoveL p10, v100, z5, tNozzle\\WObj:=wPart;      tNozzle robhold FALSE (its tframe in the world)
                                                     wPart robhold TRUE (uframe x oframe on the faceplate)

The robtarget is the stationary tool's TCP in the work object the robot holds: RAPID puts the faceplate at
tframe x inverse(p) x inverse(wobj), and a MoveL keeps the tool's TCP on a straight line through the part.

FANUC does it with the Remote TCP option (J624, measured on ROBOGUIDE V10.10, tools/make_rtcp_probe.py): the user
frame selected is the remote TCP. So the stationary tool becomes a UFRAME (its tframe, in the world) and the
robot-held work object a UTOOL (uframe x oframe, on the faceplate), the point is the inverse pose (the part seen
from the tool), and L / C moves carry the RTCP option, which keeps the tool's TCP on the line or the circle through
the part (without it, the part's origin moves straight instead):

    UFRAME_NUM=3 ;        (tNozzle)
    UTOOL_NUM=4 ;         (wPart)
    L P[2] 100mm/sec CNT5 RTCP ;

J refuses RTCP (ASBN-092): a MoveJ is written without it, to the same point (a joint move has no path to keep).
The UFRAME and UTOOL numbers are those of the frame tables (`uframes` lists the stationary tool, `utools` the
work object): a mapping file given back gives them back. A point known only at run time (a routine's parameter, an
array indexed at run time, Offs() of one, RelTool()) stays TODO: its inverse pose is not worked out on the robot.
"""

from dataclasses import replace

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.values import RobTarget, Unresolvable
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

OPTION = "J624"  # Remote TCP
RTCP = "RTCP"  # the motion option: L and C (and A) take it, J refuses it


def remote_pair(c, tool: n.Expr | None, wobj: n.Expr | None) -> bool:
    """A stationary tool (robhold FALSE) with a work object the robot holds (robhold TRUE), both named data with
    a value, the work object not moved by a mechanical unit: what Remote TCP converts."""
    if not isinstance(tool, n.Name) or not isinstance(wobj, n.Name):
        return False
    try:
        held_tool = c.declared_frame("UT", tool)
        held_wobj = c.declared_frame("UF", wobj)
    except Unresolvable:
        return False
    return not held_tool.robhold and held_wobj.robhold and not held_wobj.moving


def remote_point(value: RobTarget) -> RobTarget:
    """The P[] of a remote TCP move: the robot-held frame (UTOOL) in the stationary tool's frame (UFRAME), the inverse
    of the robtarget (the tool in the part). The arm configuration stays the robtarget's."""
    return replace(value, pose=value.pose.inverse())


class RemoteTcp:
    """The routine translator's part that writes remote TCP moves (mixed into it): needs c, name, warn()."""

    def remote_frames(self, m: n.Move) -> tuple[tuple[int, int | None], tuple[int, int | None]] | None:
        """(UFRAME, UTOOL) selections of a move with a stationary tool and a robot-held work object: the tool as the
        UFRAME, the work object as the UTOOL (a MoveAbsJ too: its joint point is recorded in the frames selected,
        INTP-253). None for any other move."""
        if not remote_pair(self.c, m.tool, m.wobj):  # type: ignore[attr-defined]
            return None
        line, c = m.span.line, self.c  # type: ignore[attr-defined]
        tool, wobj = m.tool.name, m.wobj.name  # type: ignore[union-attr]
        uf = c.frame_number("UF", m.tool, self.name, line, remote=True)  # type: ignore[attr-defined]
        ut = c.frame_number("UT", m.wobj, self.name, line, remote=True)  # type: ignore[attr-defined]
        self.remote_pending = (tool, wobj, uf, ut)
        return c.selection("UF", uf), c.selection("UT", ut)

    def remote_written(self, line: int) -> None:
        """The remote TCP move is written: its frames listed, and said once (the option it needs)."""
        c, pair = self.c, self.remote_pending  # type: ignore[attr-defined]
        if pair in c.result.remote_tcp:
            return
        c.result.remote_tcp.append(pair)
        tool, wobj, uf, ut = pair
        c.note(self.name, line, "WARNING",  # type: ignore[attr-defined]
               f"remote TCP: the moves with the stationary tool {tool} and the robot-held work object {wobj} are"
               f" written with RTCP (L and C; J without it), UFRAME[{uf}] = {tool} (in the world), UTOOL[{ut}] ="
               f" {wobj} (on the faceplate), each P[] the part seen from the tool: the controller needs the Remote"
               f" TCP option ({OPTION})", Blocker.STATIONARY)  # fmt: skip

    def remote_argument(self, expr: n.Expr, slot: str, routine: str, tool: n.Name, wobj: n.Name, line: int) -> str:
        """P[j] a robtarget argument is passed from (`PR[k]=P[j]`) when the routine moves to it with a stationary tool
        and a robot-held work object: the point known now, inverted, recorded in the remote TCP frames."""
        base = expr.args[0].value if isinstance(expr, n.FuncCall) and expr.name.upper() == "OFFS" and expr.args else expr
        try:
            if self.point_source(base) is not None:  # type: ignore[attr-defined, arg-type]
                raise Unresolvable("a point kept in a position register")
            value = self.c.evaluator.robtarget(expr)  # type: ignore[attr-defined]
        except Unresolvable as exc:
            raise Untranslatable(
                f"argument {slot}: {routine} moves to it with the stationary tool {tool.name} and the robot-held work"
                f" object {wobj.name} (remote TCP), and '{format_expr(expr)}' is only known at run time ({exc}): its"
                " P[] is the inverse pose (the part seen from the tool), which the robot does not work out",
                Blocker.STATIONARY) from exc  # fmt: skip
        c = self.c  # type: ignore[attr-defined]
        uf = c.selection("UF", c.frame_number("UF", tool, self.name, line, remote=True))  # type: ignore[attr-defined]
        ut = c.selection("UT", c.frame_number("UT", wobj, self.name, line, remote=True))  # type: ignore[attr-defined]
        return self.point(expr, remote_point(value), uf, ut, line)  # type: ignore[attr-defined]

    def remote_passed(self, m: n.Move) -> bool:
        """A remote TCP move to points the routine is given as they are (no Offs(), no RelTool()), every caller
        passing them inverted (remote_argument): those of a routine moving to them with these very frames."""
        names = [p for p in (m.to_point, m.via_point) if p is not None]
        args = self.args  # type: ignore[attr-defined]
        if args is None or not all(isinstance(p, n.Name) and args.kind(p.name) == "robtarget" for p in names):
            return False
        for p in names:
            tool, wobj = self.c.point_frames(args.routine, p.name)  # type: ignore[attr-defined, union-attr]
            if not (isinstance(tool, n.Name) and isinstance(wobj, n.Name) and tool.name.upper() == m.tool.name.upper()  # type: ignore[union-attr]
                    and wobj.name.upper() == m.wobj.name.upper()):  # type: ignore[union-attr]
                return False
        return True

    @staticmethod
    def remote_refused(m: n.Move) -> Untranslatable:
        """A remote TCP move to a point only known at run time."""
        return Untranslatable(
            f"remote TCP move (stationary tool {m.tool.name}, robot-held work object {m.wobj.name}) to a point"  # type: ignore[union-attr]
            " only known at run time: its P[] is the inverse pose (the part seen from the tool), which the robot does"
            " not work out from a position register; give the point its value in the backup, or teach it with RTCP",
            Blocker.STATIONARY,
        )  # fmt: skip
