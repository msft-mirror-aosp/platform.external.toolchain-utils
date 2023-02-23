#!/usr/bin/env python3
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities to file bugs."""

import datetime
import enum
import json
import os
import threading
from typing import Any, Dict, List, Optional


X20_PATH = "/google/data/rw/teams/c-compiler-chrome/prod_bugs"

# These constants are sourced from
# //google3/googleclient/chrome/chromeos_toolchain/bug_manager/bugs.go
class WellKnownComponents(enum.IntEnum):
    """A listing of "well-known" components recognized by our infra."""

    CrOSToolchainPublic = -1
    CrOSToolchainPrivate = -2
    AndroidRustToolchain = -3


class _FileNameGenerator:
    """Generates unique file names. This container is thread-safe.

    The names generated have the following properties:
        - successive, sequenced calls to `get_json_file_name()` will produce
          names that sort later in lists over time (e.g.,
          [generator.generate_json_file_name() for _ in range(10)] will be in
          sorted order).
        - file names cannot collide with file names generated on the same
          machine (ignoring machines with unreasonable PID reuse).
        - file names are incredibly unlikely to collide when generated on
          multiple machines, as they have 8 bytes of entropy in them.
    """

    _RANDOM_BYTES = 8
    _MAX_OS_ENTROPY_VALUE = 1 << _RANDOM_BYTES * 8
    # The intent of this is "the maximum possible size of our entropy string,
    # so we can zfill properly below." Double the value the OS hands us, since
    # we add to it in `generate_json_file_name`.
    _ENTROPY_STR_SIZE = len(str(2 * _MAX_OS_ENTROPY_VALUE))

    def __init__(self):
        self._lock = threading.Lock()
        self._entropy = int.from_bytes(
            os.getrandom(self._RANDOM_BYTES), byteorder="little", signed=False
        )

    def generate_json_file_name(self, now: datetime.datetime):
        with self._lock:
            my_entropy = self._entropy
            self._entropy += 1

        now = now.isoformat("T", "seconds") + "Z"
        entropy_str = str(my_entropy).zfill(self._ENTROPY_STR_SIZE)
        pid = os.getpid()
        return f"{now}_{entropy_str}_{pid}.json"


_GLOBAL_NAME_GENERATOR = _FileNameGenerator()


def _WriteBugJSONFile(object_type: str, json_object: Dict[str, Any]):
    """Writes a JSON file to X20_PATH with the given bug-ish object."""
    final_object = {
        "type": object_type,
        "value": json_object,
    }

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    file_path = os.path.join(
        X20_PATH, _GLOBAL_NAME_GENERATOR.generate_json_file_name(now)
    )
    temp_path = file_path + ".in_progress"
    try:
        with open(temp_path, "w") as f:
            json.dump(final_object, f)
        os.rename(temp_path, file_path)
    except:
        os.remove(temp_path)
        raise
    return file_path


def AppendToExistingBug(bug_id: int, body: str):
    """Sends a reply to an existing bug."""
    _WriteBugJSONFile(
        "AppendToExistingBugRequest",
        {
            "body": body,
            "bug_id": bug_id,
        },
    )


def CreateNewBug(
    component_id: int,
    title: str,
    body: str,
    assignee: Optional[str] = None,
    cc: Optional[List[str]] = None,
):
    """Sends a request to create a new bug.

    Args:
      component_id: The component ID to add. Anything from WellKnownComponents
        also works.
      title: Title of the bug. Must be nonempty.
      body: Body of the bug. Must be nonempty.
      assignee: Assignee of the bug. Must be either an email address, or a
        "well-known" assignee (detective, mage).
      cc: A list of emails to add to the CC list. Must either be an email
        address, or a "well-known" individual (detective, mage).
    """
    obj = {
        "component_id": component_id,
        "subject": title,
        "body": body,
    }

    if assignee:
        obj["assignee"] = assignee

    if cc:
        obj["cc"] = cc

    _WriteBugJSONFile("FileNewBugRequest", obj)


def SendCronjobLog(cronjob_name: str, failed: bool, message: str):
    """Sends the record of a cronjob to our bug infra.

    cronjob_name: The name of the cronjob. Expected to remain consistent over
      time.
    failed: Whether the job failed or not.
    message: Any seemingly relevant context. This is pasted verbatim in a bug, if
      the cronjob infra deems it worthy.
    """
    _WriteBugJSONFile(
        "CronjobUpdate",
        {
            "name": cronjob_name,
            "message": message,
            "failed": failed,
        },
    )
