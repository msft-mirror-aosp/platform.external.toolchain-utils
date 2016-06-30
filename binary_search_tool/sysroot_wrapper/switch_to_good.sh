#!/bin/bash -u

source common/common.sh

cat $1 > ${bisect_dir}/GOOD_SET

grep -v -x -F -f $1 ${bisect_dir}/BAD_SET > ${bisect_dir}/BAD_SET.tmp
mv ${bisect_dir}/BAD_SET.tmp ${bisect_dir}/BAD_SET

exit 0
