#!/bin/bash -eu

# This script generates warnings_pb2.py for use by clang_tidy_warn.py and
# clang_tidy_warn_test.py.
#
# This script is dependent on having protoc. If you do not have it, check
# Team Tools and Scripts for installing protoc
mydir=$(dirname "$(readlink -m "$0")")
protoc --python_out="${mydir}" --proto_path "${mydir}" warnings.proto
