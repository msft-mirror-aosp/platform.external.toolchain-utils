#!/bin/bash -u
#
# Copyright 2016 Google Inc. All Rights Reserved.
#
# This script calls build_image to generate a new ChromeOS image,
# using whatever packages are currently in the build tree.  If
# build_images succeeeds, then it pushes the new ChromeOS image onto a
# chromebook. If pushing the ChromeOS image onto the chromebook fails it
# will walk the user through troubleshooting the problem.
#
# This script is intended to be used by binary_search_state.py, as
# part of the binary search triage on ChromeOS packages. It should return '0'
# if the install succeeds; and '1' if the install fails (the image could not
# build or be flashed).
#

export PYTHONUNBUFFERED=1

source cros_pkg_common.sh

usb_flash()
{
  echo
  echo "Insert a usb stick into the current machine"
  echo "Note: The cros flash will take time and doesn't given much output."
  echo "      Be patient. If your usb access light is flashing it's working."
  sleep 1
  read -p "Press enter to continue" notused

  cros flash --board=${BOARD} --clobber-stateful usb:// ~/trunk/src/build/images/${BOARD}/latest/chromiumos_test_image.bin

  echo
  echo "Flash to usb complete!"
  echo "Plug the usb into your chromebook and install the image."
  echo "Refer to the ChromiumOS Developer's Handbook for more details."
  echo "http://www.chromium.org/chromium-os/developer-guide#TOC-Boot-from-your-USB-disk"
  while true; do
    sleep 1
    read -p "Was the installation of the image successful? " choice
    case $choice in
        [Yy]*) return 0;;
        [Nn]*) return 1;;
        *) echo "Please answer y or n.";;
    esac
  done
}

ethernet_flash()
{
  echo
  echo "Please ensure your Chromebook is up and running Chrome so"
  echo "cros flash may run."
  echo "If your Chromebook has a broken image you can try:"
  echo "1. Rebooting your Chromebook 6 times to install the last working image"
  echo "2. Alternatively, running the following command on the Chromebook"
  echo "   will also rollback to the last working image:"
  echo "   'update_engine_client --rollback --nopowerwash --reboot'"
  echo "3. Flashing a new image through USB"
  echo
  sleep 1
  read -p $'Press enter to continue and retry the ethernet flash' notused
  cros flash --board=${BOARD} --clobber-stateful ${REMOTE} ~/trunk/src/build/images/${BOARD}/latest/chromiumos_test_image.bin
}

echo
echo "INSTALLATION BEGIN"
echo
echo "BUILDING"
pushd ~/trunk/src/scripts
./build_image test --noeclean --board=${BOARD} --noenable_rootfs_verification
build_status=$?
popd

if [[ ${build_status} -eq 0 ]] ; then
    echo
    echo "FLASHING"
    echo "Pushing built image onto device."
    echo "cros flash --board=${BOARD} --clobber-stateful ${REMOTE} ~/trunk/src/build/images/${BOARD}/latest/chromiumos_test_image.bin"
    cros flash --board=${BOARD} --clobber-stateful ${REMOTE} ~/trunk/src/build/images/${BOARD}/latest/chromiumos_test_image.bin
    cros_flash_status=$?
    while [[ ${cros_flash_status} -ne 0 ]] ; do
        while true; do
          echo
          echo "cros flash has failed! From here you can:"
          echo "1. Flash through USB"
          echo "2. Retry flashing over ethernet"
          echo "3. Abort this installation and skip this image"
          sleep 1
          read -p "Which method would you like to do? " choice
          case $choice in
              1) usb_flash && break;;
              2) ethernet_flash && break;;
              3) exit 1;;
              *) echo "Please answer 1, 2, or 3.";;
          esac
        done

        cros_flash_status=$?
    done
else
    echo "build_image returned a non-zero status: ${build_status}"
    exit 1
fi

exit 0
