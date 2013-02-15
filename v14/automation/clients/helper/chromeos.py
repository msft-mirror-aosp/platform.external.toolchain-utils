#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

__author__ = 'kbaclawski@google.com (Krystian Baclawski)'

import os.path

from automation.common import job
from automation.common import machine
from automation.clients.helper import jobs


class JobsFactory(object):
  def __init__(self, toolchain="v1", board="x86-generic", p4_snapshot=""):
    self.toolchain = toolchain
    self.board = board
    self.p4_snapshot = p4_snapshot

    toolchain_path = os.path.join(jobs.P4_CHECKOUT_DIR,
                                  jobs.GetToolchainPath(toolchain))

    self.tc_pkgs_path = os.path.join(toolchain_path, "output/pkgs")
    self.tc_objs_path = os.path.join(toolchain_path, "output/objects")

  @staticmethod
  def CreateChromeOSJob(label, command, lock=True):
    new_job = jobs.CreateLinuxJob(label, command, lock)
    new_job.DependsOnMachine(
        machine.MachineSpecification("*", "chromeos", lock), False)
    return new_job

  def BuildToolchain(self):
    command = jobs.GetBuildToolchainCommand(toolchain=self.toolchain,
                                            board=self.board,
                                            p4_snapshot=self.p4_snapshot)
    label = 'BuildToolchain(%s,%s)' % (self.toolchain, self.board)
    new_job = jobs.CreateLinuxJob(label, command)
    tc_pkgs_dep = job.FolderDependency(new_job, self.tc_pkgs_path)
    tc_objs_dep = job.FolderDependency(new_job, self.tc_objs_path)
    return new_job, tc_pkgs_dep, tc_objs_dep

  def BuildAndTestChromeOS(self, version, tc_pkgs_dep):
    command = jobs.GetBuildAndTestChromeOSCommand(version,
                                                  toolchain=self.toolchain,
                                                  board=self.board,
                                                  p4_snapshot=self.p4_snapshot)
    label = 'BuildAndTestChromeOS(%s,%s,%s)' % (self.toolchain, self.board,
                                                version)
    new_job = self.CreateChromeOSJob(label, command)
    new_job.DependsOnFolder(tc_pkgs_dep)
    return new_job

  def RunDejaGNU(self, tc_pkgs_dep, tc_objs_dep):
    command = jobs.GetDejaGNUCommand(toolchain=self.toolchain, board=self.board,
                                     p4_snapshot=self.p4_snapshot)
    label = 'RunDejaGNU(%s,%s)' % (self.toolchain, self.board)
    new_job = self.CreateChromeOSJob(label, command)
    new_job.DependsOnFolder(tc_pkgs_dep)
    new_job.DependsOnFolder(tc_objs_dep)
    return new_job

  def RunPerflab(self, version, benchmark, tc_pkgs_dep):
    command = jobs.GetPerflabCommand(version, benchmark,
                                     toolchain=self.toolchain, board=self.board,
                                     p4_snapshot=self.p4_snapshot)
    label = 'RunPerflab(%s,%s,%s,[%s])' % (self.toolchain, self.board, version,
                                           benchmark)
    new_job = jobs.CreateLinuxJob(label, command, lock=True)
    new_job.DependsOnFolder(tc_pkgs_dep)
    return new_job

  def RunUpdate(self, version):
    command = jobs.GetUpdateCommand(version, boards=self.board)
    label = "RunUpdate(%s,%s)" % (self.board, version)
    return jobs.CreateLinuxJob(label, command)
