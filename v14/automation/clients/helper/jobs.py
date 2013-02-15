#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import os.path
import re

from automation.common import command as cmd
from automation.common import job
from automation.common import machine
from utils import logger
from automation.clients.helper import perforce


def CreateLinuxJob(label, command, lock=False):
  to_return = job.Job(label, command)
  to_return.DependsOnMachine(
      machine.MachineSpecification(os="linux", lock_required=lock))
  return to_return


def MakeSymlink(to_path, link_name):
  return cmd.Shell("ln", "-f", "-s", "-T", to_path, link_name)


def MakeDir(*dirs):
  return cmd.Shell("mkdir", "-p", *dirs)


def SyncDir(from_dir, to_dir):
  return cmd.Shell("rsync", "-a",
                   from_dir.rstrip("/") + "/",
                   to_dir.rstrip("/") + "/")


def UnTar(tar_file, dest_dir):
  return cmd.Chain(
      MakeDir(dest_dir),
      cmd.Shell("tar", "-x", "-f", tar_file, "-C", dest_dir))


def NewChain(*commands):
  return cmd.Chain(
      cmd.Shell("pwd"),
      cmd.Shell("uname", "-a"),
      *commands)
