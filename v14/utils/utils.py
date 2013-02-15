#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Utilities for toolchain build."""

__author__ = "asharif@google.com (Ahmad Sharif)"

import hashlib
import os
import re
import logger


def GetRoot(scr_name):
  """Break up pathname into (dir+name)."""
  abs_path = os.path.abspath(scr_name)
  return (os.path.dirname(abs_path), os.path.basename(abs_path))


def FormatQuotedCommand(command):
  return command.replace("\"", "\\\"")


def FormatCommands(commands):
  output = str(commands)
  output = re.sub("&&", "&&\n", output)
  output = re.sub(";", ";\n", output)
  output = re.sub("\n+\s*", "\n", output)
  return output


def GetBuildPackagesCommand(board):
  return "./build_packages --nousepkg --withdev --withtest --withautotest " \
         "--skip_toolchain_update --board=%s" % board


def GetBuildImageCommand(board):
  return "./build_image --withdev --board=%s" % board


def GetModImageForTestCommand(board):
  return "./mod_image_for_test.sh --yes --board=%s" % board


def GetSetupBoardCommand(board, gcc_version=None, binutils_version=None,
                         usepkg=None, force=None):
  options = []

  if gcc_version:
    options.append("--gcc_version=%s" % gcc_version)

  if binutils_version:
    options.append("--binutils_version=%s" % binutils_version)

  if usepkg:
    options.append("--usepkg")
  else:
    options.append("--nousepkg")

  if force:
    options.append("--force")

  return "./setup_board --board=%s %s" % (board, " ".join(options))


def Md5File(filename, block_size=2**10):
  md5 = hashlib.md5()

  try:
    with open(filename) as f:
      while True:
        data = f.read(block_size)
        if not data:
          break
        md5.update(data)
  except IOError as ex:
    logger.GetLogger().LogFatal(ex)

  return md5.hexdigest()


def GetP4ClientSpec(client_name, p4_paths):
  p4_string = ""
  for p4_path in p4_paths:
    if " " not in p4_path:
      p4_string += p4_path
    else:
      [remote_path, local_path] = p4_path.split()
      if local_path.endswith("/") and not remote_path.endswith("/"):
        local_path = "%s%s" % (local_path, os.path.basename(remote_path))
      p4_string += " -a \"%s //%s/%s\"" % (remote_path, client_name, local_path)

  return p4_string


def GetP4SyncCommand(revision=None):
  command = "g4 sync"
  if revision:
    command += " @%s" % revision
  return command


def GetP4SetupCommand(client_name, port, mappings,
                      checkout_dir=None):
  command = "export P4CONFIG=.p4config"
  if checkout_dir:
    command += "&& mkdir -p %s && cd %s" % (checkout_dir, checkout_dir)
  command += "&& cp ${HOME}/.p4config ."
  command += "&& chmod u+w .p4config"
  command += "&& echo \"P4PORT=%s\" >> .p4config" % port
  command += "&& echo \"P4CLIENT=%s\" >> .p4config" % client_name
  command += "&& g4 client " + GetP4ClientSpec(client_name, mappings)
  return command


def GetP4VersionCommand(client_name, checkout_dir):
  command = "cd %s" % checkout_dir
  command += "&& g4 changes -m1 ...#have | grep -o 'Change [0-9]\+' | cut -d' ' -f2"
  return command


def GetP4DeleteCommand(client_name, checkout_dir=None):
  command = ""
  if checkout_dir:
    command += "cd %s &&" % checkout_dir
  command += "g4 client -d %s" % client_name
  return command
