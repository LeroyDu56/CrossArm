# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Licence files: who may use CrossArm in production, checked offline.

CrossArm is published under the Business Source License 1.1: evaluating it is free,
production use needs a commercial licence. The code is public, so nothing here can stop
someone determined, and nothing tries to: every feature works without a licence. What
changes is what the output says. Without a licence, every program CrossArm writes starts
by saying it is an evaluation copy, and so does the report, so a converted program
delivered to a customer is recognisable as such. With a licence, the mark names the
licence instead. Removing the mark from the code does not grant any right: see
LICENSING.md.

A licence is a short text file signed with the licensor's private key, which never
leaves the licensor's computer. PUBLIC_KEY below checks the signature (Ed25519, RFC 8032,
written here in plain Python since CrossArm has no dependency). Nothing is sent anywhere.

    crossarm licence
    Licensee: ACME Robotics
    Licence: RC-2026-0001
    Valid until: 2027-09-30
    Signature: <base64>

CrossArm looks for it in $CROSSARM_LICENCE, next to CrossArm.exe, then in the CrossArm folder of
the user's local application data (where the window's "Install a licence" copies it).
"""

import base64
import hashlib
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

LICENCE_FILE = "crossarm.licence"
CONTACT = "enzoleroy56@gmail.com"
# The licensor's public key. Its private half signs licences and is kept outside this repository.
PUBLIC_KEY = bytes.fromhex("993e1850ade0ea3641288535de36e8276da160cdb714e5a8a51599353b959eb9")
_FIELDS = ("Licensee", "Licence", "Valid until")

# -- Ed25519 (RFC 8032, section 6: the reference algorithm) ------------------------------------

_P = 2**255 - 19
_Q = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)
Point = tuple[int, int, int, int]  # extended coordinates X, Y, Z, T


def _hash_mod_q(data: bytes) -> int:
    return int.from_bytes(hashlib.sha512(data).digest(), "little") % _Q


def _add(p: Point, q: Point) -> Point:
    a = (p[1] - p[0]) * (q[1] - q[0]) % _P
    b = (p[1] + p[0]) * (q[1] + q[0]) % _P
    c = 2 * p[3] * q[3] * _D % _P
    d = 2 * p[2] * q[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _mul(scalar: int, point: Point) -> Point:
    result: Point = (0, 1, 1, 0)
    while scalar:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _equal(p: Point, q: Point) -> bool:
    return (p[0] * q[2] - q[0] * p[2]) % _P == 0 and (p[1] * q[2] - q[1] * p[2]) % _P == 0


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P:
        return None
    return _P - x if (x & 1) != sign else x


_GY = 4 * pow(5, _P - 2, _P) % _P
_GX = _recover_x(_GY, 0) or 0
_G: Point = (_GX, _GY, 1, _GX * _GY % _P)


def _compress(point: Point) -> bytes:
    z_inv = pow(point[2], _P - 2, _P)
    x, y = point[0] * z_inv % _P, point[1] * z_inv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(data: bytes) -> Point | None:
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


def _expand(secret: bytes) -> tuple[int, bytes]:
    digest = hashlib.sha512(secret).digest()
    a = int.from_bytes(digest[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, digest[32:]


def public_key(secret: bytes) -> bytes:
    return _compress(_mul(_expand(secret)[0], _G))


def sign(secret: bytes, message: bytes) -> bytes:
    a, prefix = _expand(secret)
    public = _compress(_mul(a, _G))
    r = _hash_mod_q(prefix + message)
    big_r = _compress(_mul(r, _G))
    s = (r + _hash_mod_q(big_r + public + message) * a) % _Q
    return big_r + int.to_bytes(s, 32, "little")


def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    if len(public) != 32 or len(signature) != 64:
        return False
    a, r = _decompress(public), _decompress(signature[:32])
    if a is None or r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _Q:
        return False
    h = _hash_mod_q(signature[:32] + public + message)
    return _equal(_mul(s, _G), _add(r, _mul(h, a)))


# -- licence files -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Licence:
    licensee: str
    number: str
    valid_until: date


@dataclass(frozen=True, slots=True)
class LicenceStatus:
    """The licence CrossArm runs under: `licence` is None for an evaluation copy, with the reason."""

    licence: Licence | None
    reason: str = ""  # why this is an evaluation copy, when a licence file was found but not accepted
    path: Path | None = None

    @property
    def licensed(self) -> bool:
        return self.licence is not None

    def describe(self) -> str:
        """One line, for the window, the log and the report."""
        if self.licence is not None:
            lic = self.licence
            return f"Licensed to {lic.licensee} (licence {lic.number}, valid until {lic.valid_until:%Y-%m-%d})"
        why = f" ({self.reason})" if self.reason else ""
        return f"Evaluation copy{why}: production use needs a commercial licence, {CONTACT}"

    def remarks(self) -> list[str]:
        """The mark at the top of every program CrossArm writes (remarks, 32 characters at most)."""
        if self.licence is None:
            return ["CrossArm EVALUATION copy", "production use needs a licence"]
        name = self.licence.licensee.encode("ascii", "replace").decode("ascii")
        return [f"crossarm licence {self.licence.number}"[:32], name[:32]]


def _message(fields: dict[str, str]) -> bytes:
    """What is signed: the fields in a fixed order, so the file's layout does not matter."""
    return "\n".join(["crossarm licence", *(f"{key}: {fields[key]}" for key in _FIELDS)]).encode("utf-8")


def issue(secret: bytes, licensee: str, number: str, valid_until: date) -> str:
    """The text of a licence file (for the licensor's own tool: needs the private key)."""
    fields = {"Licensee": licensee.strip(), "Licence": number.strip(), "Valid until": f"{valid_until:%Y-%m-%d}"}
    signature = base64.b64encode(sign(secret, _message(fields))).decode("ascii")
    return "\n".join(["crossarm licence", *(f"{k}: {fields[k]}" for k in _FIELDS), f"Signature: {signature}", ""])


def read_licence(path: Path, today: date | None = None, key: bytes | None = None) -> LicenceStatus:
    """The status given by one licence file: licensed, or evaluation with the reason."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return LicenceStatus(None, f"licence file unreadable: {exc}", path)
    fields = {}
    for line in text.splitlines():
        name, sep, value = line.partition(":")
        if sep:
            fields[name.strip()] = value.strip()
    if any(not fields.get(name) for name in (*_FIELDS, "Signature")):
        return LicenceStatus(None, "not a crossarm licence file", path)
    try:
        signature = base64.b64decode(fields["Signature"], validate=True)
        valid_until = date.fromisoformat(fields["Valid until"])
    except ValueError:
        return LicenceStatus(None, "licence file damaged", path)
    if not verify(PUBLIC_KEY if key is None else key, _message(fields), signature):
        return LicenceStatus(None, "licence file not valid: its signature does not match", path)
    if (today or date.today()) > valid_until:
        return LicenceStatus(None, f"licence {fields['Licence']} expired on {valid_until:%Y-%m-%d}", path)
    return LicenceStatus(Licence(fields["Licensee"], fields["Licence"], valid_until), "", path)


def licence_folder() -> Path:
    """Where the window installs a licence: the CrossArm folder of the user's local application data."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "CrossArm"


def candidates() -> list[Path]:
    """Where a licence file is looked for, in order."""
    if os.environ.get("CROSSARM_LICENCE"):
        return [Path(os.environ["CROSSARM_LICENCE"])]  # set: the only place, so a test or a user can pin it
    places = []
    if getattr(sys, "frozen", False):
        places.append(Path(sys.executable).parent / LICENCE_FILE)
    places.append(licence_folder() / LICENCE_FILE)
    return places


def current() -> LicenceStatus:
    """The licence CrossArm runs under now."""
    for path in candidates():
        if path.is_file():
            return read_licence(path)
    return LicenceStatus(None)


__all__ = [
    "CONTACT", "LICENCE_FILE", "PUBLIC_KEY", "Licence", "LicenceStatus", "candidates", "current", "issue",
    "licence_folder", "public_key", "read_licence", "sign", "verify",
]  # fmt: skip
