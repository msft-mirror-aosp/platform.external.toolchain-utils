#!/bin/bash
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: raymes@google.com (Raymes Khoury)

export PYTHONPATH+=":.."
for test in $(find -name \*test.py); do
  echo RUNNING: ${test}
  if ! ./${test} ; then
    echo "Test Failed!"
    exit 1
  fi
done
