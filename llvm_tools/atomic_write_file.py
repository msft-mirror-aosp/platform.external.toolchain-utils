# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Atomic file writing utilities.

Provides atomic_write(...), which allows atomically replacing the contents
of a file.
"""

import contextlib
from pathlib import Path
from typing import Union


@contextlib.contextmanager
def atomic_write(fp: Union[Path, str], mode="w", *args, **kwargs):
    """Write to a filepath atomically.

    This works by a temp file swap, created with a .tmp suffix in
    the same directory briefly until being renamed to the desired
    filepath.

    In the event an exception is raised during the write, the
    temporary file is deleted and the original filepath is untouched.

    Args:
      fp: Filepath to open.
      mode: File mode; can be 'w', 'wb'. Default 'w'.
      *args: Passed to Path.open as nargs.
      **kwargs: Passed to Path.open as kwargs.

    Raises:
      ValueError when the mode is invalid.

    Usage:
        >>> with atomic_write("my_file.txt", encoding="utf-8") as f:
        >>>     f.write("Hello world!")
        >>>     # my_file.txt is still unmodified
        >>> # "f" is closed here, and my_file.txt is written to.
    """
    if isinstance(fp, str):
        fp = Path(fp)
    if mode not in ("w", "wb"):
        raise ValueError(f"mode {mode} not accepted")
    temp_fp = fp.with_suffix(fp.suffix + ".tmp")
    try:
        with temp_fp.open(mode, *args, **kwargs) as f:
            yield f
    except:
        if temp_fp.is_file():
            temp_fp.unlink()
        raise
    temp_fp.rename(fp)
