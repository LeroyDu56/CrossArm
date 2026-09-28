# Third-party licences

## Source code

The CrossArm source code has **no runtime dependency**: it uses the Python
standard library only. Nothing in this repository is copied from another
project.

`pytest` and `ruff` (both MIT) are development tools. They are not distributed
with CrossArm.

## CrossArm.exe

The Windows executable is built with [PyInstaller](https://pyinstaller.org/),
which bundles a Python interpreter and the libraries the program imports. The
components below are therefore redistributed inside `CrossArm.exe`, and their
licences apply to that file.

| Component | Why it is there | Licence |
|---|---|---|
| CPython | the interpreter running CrossArm | PSF License Agreement |
| Tcl/Tk | used by `tkinter` for the window | Tcl/Tk licence (BSD-style) |
| zlib, libffi, sqlite3 and other CPython support libraries | shipped inside CPython | permissive, see the CPython licence |

PyInstaller itself is GPL-2.0-or-later **with an exception that permits
building and distributing non-free programs**, including commercial ones. It
is a build tool and is not part of the distributed executable, so its terms do
not reach `CrossArm.exe`.

### CPython — PSF License Agreement

CPython is copyright © 2001-2026 Python Software Foundation; All Rights
Reserved. It is distributed under the PSF License Agreement, whose full text,
together with the licences of the third-party software bundled with CPython,
is reproduced in the `LICENSE.txt` file of the Python distribution and at
<https://docs.python.org/3/license.html>.

That file is shipped alongside `CrossArm.exe` in each release, as
`python_license.txt`.

### Tcl/Tk

```
This software is copyrighted by the Regents of the University of
California, Sun Microsystems, Inc., Scriptics Corporation, ActiveState
Corporation and other parties.  The following terms apply to all files
associated with the software unless explicitly disclaimed in
individual files.

The authors hereby grant permission to use, copy, modify, distribute,
and license this software and its documentation for any purpose, provided
that existing copyright notices are retained in all copies and that this
notice is included verbatim in any distributions. No written agreement,
license, or royalty fee is required for any of the authorized uses.
Modifications to this software may be copyrighted by their authors
and need not follow the licensing terms described here, provided that
the new terms are clearly indicated on the first page of each file where
they apply.

IN NO EVENT SHALL THE AUTHORS OR DISTRIBUTORS BE LIABLE TO ANY PARTY
FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
ARISING OUT OF THE USE OF THIS SOFTWARE, ITS DOCUMENTATION, OR ANY
DERIVATIVES THEREOF, EVEN IF THE AUTHORS HAVE BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

THE AUTHORS AND DISTRIBUTORS SPECIFICALLY DISCLAIM ANY WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.  THIS SOFTWARE
IS PROVIDED ON AN "AS IS" BASIS, AND THE AUTHORS AND DISTRIBUTORS HAVE
NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
MODIFICATIONS.

GOVERNMENT USE: If you are acquiring this software on behalf of the
U.S. government, the Government shall have only "Restricted Rights"
in the software and related documentation as defined in the Federal
Acquisition Regulations (FARs) in Clause 52.227.19 (c) (2).  If you
are acquiring the software on behalf of the Department of Defense, the
software shall be classified as "Commercial Computer Software" and the
Government shall have only "Restricted Rights" as defined in Clause
252.227-7014 (b) (3) of DFARs.  Notwithstanding the foregoing, the
authors grant the U.S. Government and others acting in its behalf
permission to use and distribute the software in accordance with the
terms specified in this license.
```

These licences cover the bundled components only. CrossArm itself is licensed
under the [Business Source License 1.1](LICENSE).
