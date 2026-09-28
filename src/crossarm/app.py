# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Entry point of the desktop application (CrossArm.exe).

    CrossArm.exe                      opens the window
    CrossArm.exe <backup or files>    what Windows passes when items are dropped on the icon:
                                     the window opens and converts them right away

CROSSARM_NO_GUI=1 runs the same conversion without a window (used to smoke-test the exe).
"""

import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    paths = [Path(p) for p in (sys.argv[1:] if argv is None else argv)]
    if os.environ.get("CROSSARM_NO_GUI") == "1":
        from crossarm import pipeline
        from crossarm.gui import close_splash

        close_splash()  # no window will replace it
        result = pipeline.run(paths)
        print(f"{result.programs} programs, {result.todo} TODO -> {result.folder}")
        return 0

    from crossarm.gui import launch

    launch(paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
