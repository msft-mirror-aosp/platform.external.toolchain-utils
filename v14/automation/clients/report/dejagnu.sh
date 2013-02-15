#!/bin/bash
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

export PYTHONPATH="$(pwd)"
export DJANGO_SETTINGS_MODULE="dejagnu.settings"

declare -r DATABASE_FILE=$(python -c \
  "import $DJANGO_SETTINGS_MODULE;print $DJANGO_SETTINGS_MODULE.DATABASE_NAME")

if [ ! -f "$DATABASE_FILE" ]; then
  django-admin sqlall dejagnu
  django-admin syncdb
fi

python dejagnu/main.py $@
