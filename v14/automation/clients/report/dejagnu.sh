#!/bin/bash
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

export PYTHONPATH="$(pwd)"
export DJANGO_SETTINGS_MODULE="dejagnu.settings"

if [ ! -f "dejagnu.db" ]; then
  django-admin sqlall dejagnu
  django-admin syncdb
fi

python dejagnu/main.py $@
