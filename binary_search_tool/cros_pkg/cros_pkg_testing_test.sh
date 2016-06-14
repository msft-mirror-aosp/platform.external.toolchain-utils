#!/bin/bash -u
#
# Copyright 2015 Google Inc. All Rights Reserved.
#
# This script is intended to be used by binary_search_state.py, as
# part of the binary search triage on ChromeOS packages. It is to be
# used for testing/development of the binary search triage tool
# itself.  It waits for the install script to build and install the
# image, then checks the hash of the chrome package being used to build.
# If the hash matches the test hash, then the image is 'good',
# otherwise it is 'bad'.  This allows the rest of the bisecting tool
# to run without requiring help from the user (as it would if we were
# dealing with a real 'bad' image).
#

source cros_pkg_common.sh

#
#Initialize the value below before using this script!!!
# e.g. if 'md5sum /build/${BOARD}/packages/chromeos-base/chromeos-chrome*' shows
#
# 6a003f76caac3cdbcf6e0f6ea307f10f  /build/daisy/packages/chromeos-base/chromeos-chrome-53.0.2754.0_rc-r1.tbz2
#
# Then initialize HASH below to '6a003f76caac3cdbcf6e0f6ea307f10f'
#
HASH=''

if [ -z "${HASH}" ]
then
    echo "ERROR: HASH must be intialized in cros_pkg_testing_test.sh"
    exit 3
fi

test_hash=$(md5sum /build/${BOARD}/packages/chromeos-base/chromeos-chrome* | awk '{print $1}')
[[ "${HASH}" == "${test_hash}" ]]
exit $?
