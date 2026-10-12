# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Print each failed test of a pytest JUnit XML file as a GitHub Actions error annotation.

    python tools/ci_annotate.py junit.xml

Annotations show on the run's page and through the public API, where the logs need a sign-in.
GitHub keeps the first 10 errors of a step.
"""

import sys
import xml.etree.ElementTree as ET


def _escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(path: str) -> int:
    failed = 0
    for case in ET.parse(path).getroot().iter("testcase"):
        for problem in [*case.findall("failure"), *case.findall("error")]:
            failed += 1
            name = f"{case.get('classname', '')}::{case.get('name', '')}"
            detail = (problem.get("message") or "") + "\n" + (problem.text or "")[-1500:]
            print(f"::error title={_escape(name).replace(':', '%3A').replace(',', '%2C')}::{_escape(detail.strip())}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
