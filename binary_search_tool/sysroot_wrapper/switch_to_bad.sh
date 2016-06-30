#!/bin/bash -u

source common/common.sh

cat $1 > ${bisect_dir}/BAD_SET

grep -v -x -F -f $1 ${bisect_dir}/GOOD_SET > ${bisect_dir}/GOOD_SET.tmp
mv ${bisect_dir}/GOOD_SET.tmp ${bisect_dir}/GOOD_SET

exit 0
