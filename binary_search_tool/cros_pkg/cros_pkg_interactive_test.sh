#!/bin/bash -u
#
# Copyright 2015 Google Inc. All Rights Reserved.
#
# This script calls build_image to generate a new ChromeOS image,
# using whatever packages are currently in the build tree.  If
# build_images succeeeds, then it pushes the new ChromeOS image onto a
# chromebook, then pings the chromebook to determine if it
# successfully booted.  It then asks the user if the image is good or not,
# allowing the user to conduct whatever tests the user wishes, and waiting
# for a response.
#
# This script is intended to be used by binary_search_state.py, as
# part of the binary search triage on ChromeOS packages.  It should
# return '0' if the test succeeds (the image is 'good'); '1' if the test
# fails (the image is 'bad'); and '2' if it could not determine
# (i.e. in this case, the image did not build).
#

source cros_pkg_common.sh

pushd ~/trunk/src/scripts
./build_image test --board=${BOARD} --noenable_rootfs_verification
build_status=$?
popd


if [[ ${build_status} -eq 0 ]] ; then
    echo "Pushing built image onto device."
    echo "cros flash --board=${BOARD} --clobber-stateful ${REMOTE} ~/trunk/src/build/images/${BOARD}/latest/chromiumos_test_image.bin"
    cros flash --board=${BOARD} --clobber-stateful ${REMOTE} ~/trunk/src/build/images/${BOARD}/latest/chromiumos_test_image.bin
    cros_flash_status=$?
    if [[ ${cros_flash_status} -ne 0 ]] ; then
	echo "cros flash failed!!"
	exit 2
    fi
else
    echo "build_image returned a non-zero status: ${build_status}"
    exit 2
fi

# Send 3 pings and wait 3 seconds for any responsed (then timeout).
ping -c 3 -W 3 ${REMOTE}
retval=$?

if [[ ${retval} -eq 0 ]]; then
    echo "ChromeOS image has been built and installed on ${REMOTE}."
else
    exit 1
fi

while true; do
    read -p "Is this a good ChromeOS image?" yn
    case $yn in
        [Yy]* ) exit 0;;
        [Nn]* ) exit 1;;
        * ) echo "Please answer yes or no.";;
    esac
done

exit 2
