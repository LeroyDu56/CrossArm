# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Why a RAPID construct stays TODO: the causes the report groups TODO entries by (Blocker), and the
exception a conversion raises with one (Untranslatable)."""


class Blocker:
    """What an integrator has to solve, rather than the individual line it happened on.

    A large backup produces hundreds of TODO entries that come down to a handful of
    causes. Every TODO carries one of these so the report can group them and show
    which chunks of work are worth doing next.
    """

    CALL_ARGS = "routine call with arguments"
    MISSING = "routine or data not in the backup"
    MOVE_ROUTINE = "move made inside a routine of the backup"
    MOVE_ROUTINE_ASSUMED = "routine converted as the move it makes"
    SAVED_FRAME = "frame value as saved in the backup"
    RUNTIME_FRAME = "frame or tool built at run time"
    RUNTIME_POSITION = "position built at run time"
    CALIBRATION = "frame or position measured on the robot (calibration)"
    PAYLOAD = "payload changed at run time"
    STATIONARY = "stationary tool or robot-held work object"
    RECORD = "record component or array element"
    NO_TP_EQUIVALENT = "RAPID instruction without a TP equivalent"
    RECORD_VALUE = "record field written as the value the programs set it to"
    SAVED_VALUE = "PERS no program changes, read at its saved value"
    LOCAL_RECORD = "record of a routine kept in registers every call shares"
    TEXT = "text kept in a string register"
    CONDITION = "condition not convertible"
    VALUE = "value not known at conversion time"
    SIGNAL = "I/O signal without a mapping"
    WAIT_TIMEOUT = "wait with a timeout"
    MESSAGE_VALUE = "TPWrite showing a value"
    MESSAGE_CUT = "TPWrite text longer than MESSAGE allows"
    CAPACITY = "more numbers used than the controller holds"
    TAKEN = "pinned number already used on the controller"
    RENAMED = "program renamed so as not to replace another"
    MOTION = "motion without a TP equivalent"
    LOOP = "loop without a TP equivalent"
    AXIS_CONVENTION = "posture converted with the measured axis conventions"
    REAL_CONTROLLER = "RobOS() taken as TRUE (real controller)"
    HANDLER = "error handler: other errors stop the program"
    OPTIONS_IGNORED = "instruction options dropped"
    PROVIDED_FUNCTION = "function provided as a TP program: TP gives no value back"
    MOTION_SETTING = "motion setting (ConfL, SingArea, AccSet, VelSet...)"
    INTERRUPT = "interrupt (CONNECT, ISignalDI...) and its TRAP"
    MONITOR = "interrupt watched by a condition monitor (checked periodically)"
    SEARCH = "search: the FANUC skip stops and fails otherwise"
    IO_ROUNDED = "I/O written approximately (pulse length)"
    INLINED = "function of the backup copied into each call"
    INTERNAL = "CrossArm internal error"
    OTHER = "other"

    @staticmethod
    def rapid(kind: str) -> str:
        """Category for a construct the parser left out of scope: 'ERROR_HANDLER' -> 'RAPID error handler'."""
        if kind == "CONNECT":
            return Blocker.INTERRUPT
        return "RAPID " + kind.replace("_", " ").lower()


class Untranslatable(Exception):
    """This RAPID construct has no faithful TP equivalent in the current scope.

    `category` is the Blocker it belongs to; the report groups TODO entries by it.
    """

    def __init__(self, message: str, category: str = Blocker.OTHER) -> None:
        super().__init__(message)
        self.category = category
