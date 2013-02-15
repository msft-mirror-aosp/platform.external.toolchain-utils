#!/bin/bash

# TODO(asharif) use locks here to prevent two processes from doing this
# simultaneously.
toolchain_setup_env()
{
  if [[ -z $FLAGS_TC_ROOT ]]
  then
    return 0
  fi
  GVSB=google_vendor_src_branch
  TC_DIRS=( $GVSB/gcc )
  for TC_DIR in ${TC_DIRS[@]}
  do
    TC_LAST_DIR=${TC_DIR##*/}
    TC_MOUNTED_PATH="$(eval readlink -f "$TC_CHROOT/$FLAGS_TC_ROOT_MOUNT/$TC_LAST_DIR")"
    if [[ -z "$(mount | grep -F "on $TC_MOUNTED_PATH ")" ]]
    then
      ! TC_PATH="$(eval readlink -e "$FLAGS_TC_ROOT/$TC_DIR")"
      TC_MOUNTED_PATH="$TC_CHROOT/$FLAGS_TC_ROOT_MOUNT/$TC_LAST_DIR"
      if [[ -z "$TC_PATH" ]]
      then
        die "$FLAGS_TC_ROOT/$TC_DIR is not a valid directory."
      fi
      if [[ -z "$TC_MOUNTED_PATH" ]]
      then
        die "$TC_CHROOT/$FLAGS_TC_ROOT_MOUNT/$TC_LAST_DIR is not a valid directory."
      fi
      info "Mounting $TC_PATH at $TC_MOUNTED_PATH."
      mkdir -p $TC_MOUNTED_PATH
      sudo mount --bind "$TC_PATH" "$TC_MOUNTED_PATH" || \
        die "Could not mount $TC_PATH at $TC_MOUNTED_PATH"
    fi
  done
}

FLAGS_TC_ROOT=""
FLAGS_TC_ROOT_MOUNT="/home/$USER/toolchain_root"
FLAGS_CHROMEOS_DIR=""

# Parse command line arguments.
# TODO(asharif): Make this into a nice loop.
for arg in "$@"
do
  PARSED=0
  value=${arg##--toolchain_root=}
  if [[ $value != $arg ]]
  then
    let PARSED++
    FLAGS_TC_ROOT=$value
  fi

  value=${arg##--chromeos_root=}
  if [[ $value != $arg ]]
  then
    FLAGS_CHROMEOS_DIR=$value
    let PARSED++
  fi

  if [[ $PARSED -eq 0 ]]
  then
    newargs+="$arg "
  fi
done

if [[ -z $FLAGS_CHROMEOS_DIR ]]
then
  cd ../../ > /dev/null
  FLAGS_CHROMEOS_DIR=$(pwd)
  cd - > /dev/null
fi

eval FLAGS_CHROMEOS_DIR=$FLAGS_CHROMEOS_DIR

if [[ ! -f $FLAGS_CHROMEOS_DIR/src/scripts/common.sh ]]
then
  echo "FATAL: Invalid ChromeOS dir. Please specify the checkout dir by passing:"
  echo "--chromeos_root="
  exit 1
fi

# Enter the scripts directory.

# Source the ChromeOS common.sh script.
. $FLAGS_CHROMEOS_DIR/src/scripts/common.sh

TC_CHROOT=$DEFAULT_CHROOT_DIR

assert_outside_chroot
assert_not_root_user

toolchain_setup_env
set -- $newargs
cd $FLAGS_CHROMEOS_DIR/src/scripts
$FLAGS_CHROMEOS_DIR/src/scripts/enter_chroot.sh $newargs
