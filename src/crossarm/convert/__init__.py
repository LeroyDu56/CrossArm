# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID -> FANUC TP conversion: evaluation of RAPID data, mapping rules, report."""

from crossarm.convert.config import ConversionConfig
from crossarm.convert.mapping import build_mapping
from crossarm.convert.report import build_report
from crossarm.convert.translate import ConversionResult, convert

__all__ = ["ConversionConfig", "ConversionResult", "build_mapping", "build_report", "convert"]
