#!/bin/bash
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: raymes@google.com (Raymes Khoury)

export PYTHONPATH+=":.."
exit_status=0
for test in $(find -name \*test.py); do
  echo RUNNING: ${test}
  if ! ./${test} ; then
    echo " "
    echo "*** Test Failed! (${test}) ***"
    echo " "
    exit_status=1
  fi
done

exit $exit_status
