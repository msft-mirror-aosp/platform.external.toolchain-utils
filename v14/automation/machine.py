#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine class description.

A machine object is an instance of this class.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import re
import sys
from utils import utils

# Common initializations
(rootdir, basename) = utils.GetRoot(sys.argv[0])
utils.InitLogger(rootdir, basename)


class Machine:
  def __init__(self, name, cpu, num_cores, os, username):
    self.name = name
    self.cpu = cpu
    self.num_cores = num_cores
    self.os = os
    self.last_updated = 0
    self.load = 0
    self.uptime = 0
    self.dead = False
    self.uses = 0
    self.locked = False
    self.username = username


  def __str__(self):
    ret = ""
    ret += "Machine Information:\n"
    ret += "Name: " + self.name + "\n"
    ret += "CPU: " + self.cpu + "\n"
    ret += "NumCores: " + str(self.num_cores) + "\n"
    ret += "OS: " + self.os + "\n"
    ret += "load: " + str(self.load) + "\n"
    ret += "uses: " + str(self.uses) + "\n"
    return ret


  def ParseUptime(self, uptime_string):
    uptime_string = uptime_string.strip()
    mo = re.search("[0-9]*\.?[0-9]+$", uptime_string)
    if not mo:
      self.dead = True
      return
    self.dead = False
    self.load = mo.group(0)


  def UpdateDynamicInfo(self):
    """Attempt to acquire information about uptime, load, etc."""
#    command = "ssh " + self.name + " -- uptime"
#    (retval, stdout, stderr) = utils.RunCommand(command, True)
#    self.ParseUptime(stdout)
    pass


def Main(argv):
  build_machine_info = Machine("ahmad.mtv", "core2duo", 4, "linux", "asharif")
  print build_machine_info


if __name__ == "__main__":
  Main(sys.argv)

