# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Contains useful constants for testing LLVM."""

from typing import Iterable

from llvm_tools import cros_cls


LLVM_NEXT_HASH = "3b5e7c83a6e226d5bd7ed2e9b67449b64812074c"
LLVM_NEXT_REV = 530567

# NOTE: Always specify patch-sets for CLs. We don't want uploads by untrusted
# users to turn into bot invocations w/ untrusted input.

# A list of CLs that constitute the current llvm-next roll.
# This is taken as the set of CLs that will be landed simultaneously in order
# to make llvm-next go live.
#
# Generally speaking, for simple rolls, this should just contain a link to the
# Manifest update CL, as well as (early on, at least) a link to a CL generated
# by upload_llvm_testing_helper_cl.py.
# pylint: disable=line-too-long
LLVM_NEXT_TESTING_CLS: Iterable[cros_cls.ChangeListURL] = (
    cros_cls.ChangeListURL.parse(url)
    for url in (
        "https://chrome-internal-review.googlesource.com/c/chromeos/manifest-internal/+/7201537/2",
        "https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/5455731/5",
        "https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/5471984/1",
        "https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/5527293/1",
        "https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/5527294/1",
        "https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/5527295/1",
        "https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/5527296/1",
        "https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/5527297/1",
        "https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/5527298/1",
    )
)
