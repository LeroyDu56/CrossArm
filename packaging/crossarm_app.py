# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""PyInstaller entry script for CrossArm.exe (see .github/workflows/release.yml)."""

from crossarm.app import main

raise SystemExit(main())
