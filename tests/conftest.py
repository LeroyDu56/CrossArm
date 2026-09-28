# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

from pathlib import Path

import pytest
from helpers import FIXTURES


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
