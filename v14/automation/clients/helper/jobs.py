#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

from automation.common import command as cmd
from automation.common import job
from automation.common import machine


def CreateLinuxJob(label, command, lock=False):
  to_return = job.Job(label, command)
  to_return.DependsOnMachine(
      machine.MachineSpecification(os="linux", lock_required=lock))
  return to_return


def MakeSymlink(to_path, link_name):
  return cmd.Shell("ln", "-f", "-s", "-T", to_path, link_name)


def MakeDir(*dirs):
  return cmd.Shell("mkdir", "-p", *dirs)


def SyncDir(from_dir, to_dir, src_host=""):
  if src_host:
    from_dir = "%s:%s" % (src_host, from_dir)
  return cmd.Shell("rsync", "-a",
                   from_dir.rstrip("/") + "/",
                   to_dir.rstrip("/") + "/")


def SyncFile(from_file, to_dir):
  return cmd.Shell("rsync", "-a", from_file, to_dir.rstrip("/") + "/")


def UnTar(tar_file, dest_dir):
  return cmd.Chain(
      MakeDir(dest_dir),
      cmd.Shell("tar", "-x", "-f", tar_file, "-C", dest_dir))


def NewChain(*commands):
  return cmd.Chain(
      cmd.Shell("pwd"),
      cmd.Shell("uname", "-a"),
      *commands)
