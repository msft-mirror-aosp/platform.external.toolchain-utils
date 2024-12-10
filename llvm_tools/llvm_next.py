# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Contains useful constants for testing LLVM."""

from typing import Iterable

from llvm_tools import cros_cls


LLVM_NEXT_HASH = "f142f8afe21bceb00fb495468aa0b5043e98c419"
LLVM_NEXT_REV = 547379

# NOTE: Always specify patch-sets for CLs. We don't want uploads by untrusted
# users to turn into bot invocations w/ untrusted input.
#
# Please note that these are (somewhat) automatically curated. See
# llvm_next_py_autoupdate.py.
# pylint: disable=line-too-long
LLVM_NEXT_TESTING_CL_URLS: Iterable[str] = (
    "https://chrome-internal-review.googlesource.com/c/chromeos/manifest-internal/+/7721626/1",
    "https://crrev.com/c/5924684/3",
)

# A list of CLs that constitute the current llvm-next roll.
# This is taken as the set of CLs that will be landed simultaneously in order
# to make llvm-next go live.
#
# Generally speaking, for simple rolls, this should just contain a link to the
# Manifest update CL, as well as (early on, at least) a link to a CL generated
# by upload_llvm_testing_helper_cl.py.
LLVM_NEXT_TESTING_CLS: Iterable[cros_cls.ChangeListURL] = tuple(
    cros_cls.ChangeListURL.parse(url) for url in LLVM_NEXT_TESTING_CL_URLS
)
