# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from whitelist import is_whitelisted

def is_built_with_clang(dso_path, producer, comp_path):
    """Check whether the compile unit is built by clang.

    Args:
        dso_path: path to the elf/dso
        producer: DW_AT_producer contains the compiler command line.
        comp_path: DW_AT_comp_dir + DW_AT_name

    Returns:
        False if compiled by gcc otherwise True
    """
    if is_whitelisted('clang_comp_path', comp_path):
        return True

    if is_whitelisted('clang_dso_path', dso_path):
        return True

    if 'clang version' not in producer:
        return False
    return True
