# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Contains useful constants for testing LLVM."""

from typing import Iterable

import cros_cls


LLVM_NEXT_HASH = "28a8f1b901389c1e478407440f7ccf2d41c71b64"
LLVM_NEXT_REV = 516547

# NOTE: Always specify patch-sets for CLs. We don't want uploads by untrusted
# users to turn into bot invocations w/ untrusted input.

# A list of CLs that constitute the current llvm-next roll.
# This is taken as the set of CLs that will be landed simultaneously in order
# to make llvm-next go live.
#
# Generally speaking, for simple rolls, this should just contain a link to the
# Manifest update CL, as well as (early on, at least) a link to a CL generated
# by upload_llvm_testing_helper_cl.py.
LLVM_NEXT_TESTING_CLS: Iterable[cros_cls.ChangeListURL] = ()
