#!/usr/bin/python

import os
import sys

if '/mnt/host/source/src/third_party/toolchain-utils/crosperf' in sys.path:
    dev_path = os.path.expanduser('~/trunk/src/platform/dev')
    sys.path.append(dev_path)
else:
    print ('This script can only be run from inside a ChromeOS chroot.  Please '
           'enter your chroot, go to ~/src/third_party/toolchain-utils/crosperf'
           ' and try again.')
    sys.exit(0)

import build_util
import xbuddy

def Main(xbuddy_string):
    if not os.path.exists('./xbuddy_config.ini'):
        config_path = os.path.expanduser('~/trunk/src/platform/dev/'
                                         'xbuddy_config.ini')
        os.symlink (config_path, './xbuddy_config.ini')
    x = xbuddy.XBuddy(manage_builds=False, static_dir='/tmp/devserver/static')
    build_id = x.Translate(os.path.split(xbuddy_string))
    return build_id

if __name__ == "__main__":
    build_id = Main(sys.argv[1])
    print build_id
    sys.exit(0)
