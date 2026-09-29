# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Licence files and the evaluation mark.

Nothing here restricts a feature: an evaluation copy converts exactly what a licensed one does.
What is checked is that the output says which one it is, and that a licence cannot be made by
anyone but the licensor — the signature is Ed25519, checked against RFC 8032's own test vectors
(the implementation also matched the `cryptography` library on random keys when it was written).
"""

import os
from datetime import date

import pytest

from crossarm import licence as lic
from crossarm import pipeline

# RFC 8032, section 7.1, tests 1 and 2.
RFC_VECTORS = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
]  # fmt: skip
TEST_SECRET = bytes(range(32))  # a key for the tests only: licences signed with it are not valid for CrossArm


@pytest.fixture
def licensor(monkeypatch):
    """CrossArm checking licences against the test key instead of the licensor's."""
    monkeypatch.setattr(lic, "PUBLIC_KEY", lic.public_key(TEST_SECRET))
    return TEST_SECRET


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(("secret", "public", "message", "signature"), RFC_VECTORS)
def test_ed25519_matches_rfc_8032(secret, public, message, signature):
    secret, public, message, signature = (bytes.fromhex(v) for v in (secret, public, message, signature))
    assert lic.public_key(secret) == public
    assert lic.sign(secret, message) == signature
    assert lic.verify(public, message, signature)
    assert not lic.verify(public, message + b"!", signature)
    assert not lic.verify(public, message, signature[:-1] + bytes([signature[-1] ^ 1]))


def test_a_licence_file_names_its_licensee(tmp_path, licensor):
    path = write(tmp_path / "crossarm.licence", lic.issue(licensor, "ACME Robotics", "RC-2026-0001", date(2027, 9, 30)))
    status = lic.read_licence(path, today=date(2026, 9, 24))
    assert status.licensed and status.licence == lic.Licence("ACME Robotics", "RC-2026-0001", date(2027, 9, 30))
    assert status.describe() == "Licensed to ACME Robotics (licence RC-2026-0001, valid until 2027-09-30)"
    assert status.remarks() == ["crossarm licence RC-2026-0001", "ACME Robotics"]


def test_a_licence_cannot_be_edited_forged_or_outlived(tmp_path, licensor):
    text = lic.issue(licensor, "ACME Robotics", "RC-2026-0001", date(2027, 9, 30))
    edited = write(tmp_path / "edited.licence", text.replace("ACME Robotics", "Other Corp"))
    assert lic.read_licence(edited).reason == "licence file not valid: its signature does not match"
    forged = write(tmp_path / "forged.licence", lic.issue(os.urandom(32), "Other Corp", "X", date(2030, 1, 1)))
    assert not lic.read_licence(forged).licensed
    valid = write(tmp_path / "valid.licence", text)
    assert lic.read_licence(valid, today=date(2027, 10, 1)).reason == "licence RC-2026-0001 expired on 2027-09-30"
    assert lic.read_licence(write(tmp_path / "x.licence", "hello")).reason == "not a crossarm licence file"


def test_the_real_key_rejects_test_licences(tmp_path):
    path = write(tmp_path / "crossarm.licence", lic.issue(TEST_SECRET, "ACME", "RC-1", date(2030, 1, 1)))
    assert not lic.read_licence(path).licensed


def test_an_evaluation_copy_says_so_everywhere(tmp_path, fixtures_dir, monkeypatch):
    monkeypatch.setenv("CROSSARM_LICENCE", str(tmp_path / "none.licence"))
    logs: list[str] = []
    run = pipeline.run([fixtures_dir / "rapid" / "pick_and_place.mod"], output=tmp_path / "out", log=logs.append)
    assert not run.licence.licensed
    assert logs[0].startswith("Evaluation copy: production use needs a commercial licence")
    for program in ("MAIN", "PICK", "PLACE", "SETUP_FRAMES"):
        text = (tmp_path / "out" / f"{program}.LS").read_bytes().decode("ascii")
        body = text.split("/MN\r\n", 1)[1]
        assert body.startswith("   1:  !CrossArm EVALUATION copy ;\r\n   2:  !production use needs a licence ;\r\n")
    report = (tmp_path / "out" / "crossarm_report.md").read_text(encoding="utf-8")
    assert "> **Evaluation copy.** CrossArm is free to evaluate." in report


def test_a_licensed_copy_names_the_licence_instead(tmp_path, fixtures_dir, monkeypatch, licensor):
    path = write(tmp_path / "crossarm.licence", lic.issue(licensor, "ACME Robotics", "RC-2026-0001", date(2099, 1, 1)))
    monkeypatch.setenv("CROSSARM_LICENCE", str(path))
    run = pipeline.run([fixtures_dir / "rapid" / "pick_and_place.mod"], output=tmp_path / "out", log=lambda _: None)
    assert run.licence.licensed
    body = (tmp_path / "out" / "MAIN.LS").read_bytes().decode("ascii").split("/MN\r\n", 1)[1]
    assert body.startswith("   1:  !crossarm licence RC-2026-0001 ;\r\n   2:  !ACME Robotics ;\r\n")
    report = (tmp_path / "out" / "crossarm_report.md").read_text(encoding="utf-8")
    assert "- Licence: Licensed to ACME Robotics" in report and "Evaluation copy" not in report


def test_where_a_licence_is_looked_for(tmp_path, monkeypatch):
    monkeypatch.delenv("CROSSARM_LICENCE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert lic.candidates()[-1] == tmp_path / "CrossArm" / "crossarm.licence"
    monkeypatch.setenv("CROSSARM_LICENCE", str(tmp_path / "pinned.licence"))
    assert lic.candidates() == [tmp_path / "pinned.licence"]
    assert lic.current() == lic.LicenceStatus(None)  # nothing there: evaluation, no complaint


def test_a_condition_program_carries_no_mark(tmp_path, fixtures_dir, monkeypatch):
    """It holds WHEN lines only: the controller refuses a remark in one (ROBOGUIDE, ASBN-092). Its TRAP is marked."""
    monkeypatch.setenv("CROSSARM_LICENCE", str(tmp_path / "none.licence"))
    probe = fixtures_dir / "probes" / "interrupts" / "IntProbe.mod"
    pipeline.run([probe], output=tmp_path / "out", log=lambda _: None)
    condition = (tmp_path / "out" / "IEDGE.LS").read_bytes().decode("ascii")
    assert condition.startswith("/PROG  IEDGE\t  Cond\r\n")
    assert condition.split("/MN\r\n", 1)[1].startswith("   1:  WHEN DO[")
    trap = (tmp_path / "out" / "TEDGE.LS").read_bytes().decode("ascii").split("/MN\r\n", 1)[1]
    assert trap.startswith("   1:  !CrossArm EVALUATION copy ;")
