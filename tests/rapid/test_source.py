# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

from crossarm.rapid.source import decode, normalise_newlines, read_source


def test_utf8_is_preferred():
    assert decode("réglage".encode()) == ("réglage", "utf-8")


def test_utf8_bom_is_stripped():
    assert decode(b"\xef\xbb\xbfMODULE A") == ("MODULE A", "utf-8-sig")


def test_falls_back_to_cp1252():
    assert decode("réglage".encode("cp1252")) == ("réglage", "cp1252")


def test_crlf_and_cr_are_normalised():
    assert normalise_newlines("a\r\nb\rc\n") == "a\nb\nc\n"


def test_read_source_on_legacy_fixture(fixtures_dir):
    source = read_source(fixtures_dir / "rapid" / "legacy_header.mod")
    assert source.encoding == "cp1252"
    assert "\r" not in source.text
    assert "réglage opérateur" in source.text
