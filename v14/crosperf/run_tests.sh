#!/bin/bash
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: raymes@google.com (Raymes Khoury)

export PYTHONPATH+=":.."
for test in $(find -name \*unittest.py); do
  ./${test} || echo "Test Failed!" && exit 1
done
