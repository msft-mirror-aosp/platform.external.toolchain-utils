#!/bin/bash

. ~/trunk/src/scripts/common.sh
. ~/trunk/src/scripts/remote_access.sh

DEFINE_boolean init $FLAGS_FALSE "Init remote access."
DEFINE_boolean cleanup $FLAGS_FALSE "Cleanup remote access."

set -e

FLAGS "$@" || exit 1

TMP=/tmp/chromeos-toolchain

if [ $FLAGS_init -eq $FLAGS_TRUE ] ; then
	echo "Initting access"
	mkdir -p ${TMP}
	remote_access_init
	ssh -t -t -p 22 root@${FLAGS_remote} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/chromeos-toolchain/known_hosts -M -S ${TMP}/%r@%h:%p 2>&1 > /dev/null & 
	echo $! > ${TMP}/master-pid
fi

if [ $FLAGS_cleanup -eq $FLAGS_TRUE ] ; then
	echo "Cleaning up access"
	set +e
	kill -9 `cat ${TMP}/master-pid`
	set -e
	cleanup_remote_access
	rm -rf ${TMP}
fi

echo "Done"
