#!/bin/bash -u
#
# Copyright 2015 Google Inc. All Rights Reserved.
#
# This script pings the chromebook to determine if it has successfully booted.
#
# This script is intended to be used by binary_search_state.py, as
# part of the binary search triage on ChromeOS packages. It waits for the
# install script to build and install the image, then pings the machine.
# It should return '0' if the test succeeds (the image booted); '1' if the test
# fails (the image did not boot); and '2' if it could not determine (does not
# apply in this case).
#

source cros_pkg/common.sh

# Send 3 pings and wait 3 seconds for any responsed (then timeout).
ping -c 3 -W 3 ${REMOTE}
retval=$?


exit $retval
