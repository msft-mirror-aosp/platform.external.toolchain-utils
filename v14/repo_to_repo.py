#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

__author__ = "asharif@google.com (Ahmad Sharif)"

import getpass
import optparse
import os
import re
import socket
import sys
import tempfile
from utils import command_executer
from utils import logger
from utils import utils
from automation.clients.helper import perforce
from automation.common import command as cmd


def GetCanonicalMappings(mappings):
  canonical_mappings = []
  for mapping in mappings:
    remote_path, local_path = mapping.split()
    if local_path.endswith("/") and not remote_path.endswith("/"):
      local_path = os.path.join(local_path, os.path.basename(remote_path))
    remote_path = remote_path.lstrip('/').split('/', 1)[1]
    canonical_mappings.append(perforce.PathMapping(remote_path, local_path))
  return canonical_mappings

def SplitMapping(mapping):
  if " " in mapping:
    remote_path, local_path = mapping.split()
  else:
    local_path = "."
    remote_path = mapping
  return remote_path, local_path


class Repo(object):
  def __init__(self):
    self.repo_type = None
    self.address = None
    self.mappings = None
    self.revision = None
    self.ignores = []
    self.ignores.append(".gitignore")
    self.ignores.append(".p4config")
    self.ignores.append("README.google")
    self._root_dir = tempfile.mkdtemp()
    self._ce = command_executer.GetCommandExecuter()
    self._logger = logger.GetLogger()

  def PullSources(self):
    """ Pull all sources into an internal dir."""
    pass

  def SetupForPush(self):
    """ Setup a repository for pushing later."""
    pass

  def PushSources(self, commit_message, dry_run=False):
    """ Push to the external repo with the commit message."""
    pass

  def _RsyncExcludingRepoDirs(self, source_dir, dest_dir):
    command = "rsync -a --exclude=.git --exclude=.svn %s/ %s/" % (source_dir,
                                                               dest_dir)
    return self._ce.RunCommand(command)

  def MapSources(self, dest_dir):
    """Copy sources from the internal dir to root_dir."""
    return self._RsyncExcludingRepoDirs(self._root_dir, dest_dir)

  def GetRoot(self):
    return self._root_dir

  def CleanupRoot(self):
    command = "rm -rf %s" % self._root_dir
    return self._ce.RunCommand(command)

  def __str__(self):
    return "\n".join(str(s) for s in [self.repo_type,
                                      self.address,
                                      self.mappings])


class P4Repo(Repo):
  def __init__(self, address, mappings):
    Repo.__init__(self)
    self.repo_type = "p4"
    self.address = address
    self.mappings = mappings

  def PullSources(self):
    client_name = socket.gethostname()
    client_name += tempfile.mkstemp()[1].replace("/", "-")
    mappings = self.mappings
    port = self.address
    p4view = perforce.View("depot2",
                           GetCanonicalMappings(mappings))
    p4client = perforce.CommandsFactory(self._root_dir, p4view, name=client_name)
    command = p4client.SetupAndDo(p4client.Sync())
    ret = self._ce.RunCommand(str(command))
    assert ret == 0, "Could not setup client."
    command = p4client.InCheckoutDir(p4client.SaveCurrentCLNumber())
    ret, o, e = self._ce.RunCommand(str(command), return_output=True)
    assert ret == 0, "Could not get version from client."
    self.revision = re.search("^\d+$", o.strip(), re.MULTILINE).group(0)
    command = p4client.InCheckoutDir(p4client.Remove())
    ret = self._ce.RunCommand(str(command))
    assert ret == 0, "Could not delete client."
    return 0


class SvnRepo(Repo):
  def __init__(self, address, mappings):
    Repo.__init__(self)
    self.repo_type = "svn"
    self.address = address
    self.mappings = mappings

  def PullSources(self):
    with utils.CWDSwitcher(self._root_dir):
      for mapping in self.mappings:
        remote_path, local_path = SplitMapping(mapping)
        command += "svn co %s/%s %s" % (self.address, remote_path, local_path)
      ret = self._ce.RunCommand(command)
      if ret: return ret

      self.revision = ""
      for mapping in self.mappings:
        remote_path, local_path = SplitMapping(mapping)
        command = "cd %s && svnversion ." % (local_path)
        ret, o, e = self._ce.RunCommand(command, return_output=True)
        self.revision += o.strip()
        if ret: return ret
    return 0


class GitRepo(Repo):
  def __init__(self, address, branch, mappings=None, ignores=None):
    Repo.__init__(self)
    self.repo_type = "git"
    self.address = address
    if not branch:
      self.branch = "master"
    else:
      self.branch = branch
    if ignores:
      self.ignores += ignores
    self.mappings = mappings

  def _CloneSources(self):
    with utils.CWDSwitcher(self._root_dir):
      command = "git clone %s ." % (self.address)
      return self._ce.RunCommand(command)

  def PullSources(self):
    with utils.CWDSwitcher(self._root_dir):
      ret = self._CloneRepo()
      if ret: return ret

      command = "git checkout %s" % self.branch
      ret = self._ce.RunCommand(command)
      if ret: return ret

      command = "git describe --always"
      ret, o, e = self._ce.RunCommand(command, return_output=True)
      self.revision = o.strip()
      return ret

  def SetupForPush(self):
    with utils.CWDSwitcher(self._root_dir):
      ret = self._CloneSources()
      logger.GetLogger().LogFatalIf(ret, "Could not clone git repo %s." %
                                    self.address)

      command = "git branch -a | grep -wq %s" % self.branch
      ret = self._ce.RunCommand(command)

      if ret == 0:
        if self.branch != "master":
          command = ("git branch --track %s remotes/origin/%s" %
                      (self.branch, self.branch))
        else:
          command = "pwd"
        command += "&& git checkout %s" % self.branch
      else:
        command = "git symbolic-ref HEAD refs/heads/%s" % self.branch
      command += "&& rm -rf *"
      ret = self._ce.RunCommand(command)
      return ret

  def PushSources(self, commit_message, dry_run=False):
    with utils.CWDSwitcher(self._root_dir):
      push_args = ""
      if dry_run:
        push_args += " -n "

      command = "pwd"
      if self.ignores:
        for ignore in self.ignores:
          command += "&& echo \"%s\" >> .git/info/exclude" % ignore
      command += "&& git add -Av ."
      command += "&& git commit -v -m \"%s\"" % commit_message
      command += "; git push -v %s origin %s:%s" % (push_args, self.branch, self.branch)
      return self._ce.RunCommand(command)

  def MapSources(self, root_dir):
    if not self.mappings:
      return
    with utils.CWDSwitcher(self._root_dir):
      for mapping in self.mappings:
        remote_path, local_path = SplitMapping(mapping)
        remote_path.rstrip("...")
        local_path.rstrip("...")
        ret = self._RsyncExcludingRepoDirs(remote_path,
                                               os.path.join(root_dir, local_path))
        if ret: return ret
    return 0


class RepoReader():
  def __init__(self, filename):
    self.filename = filename
    self.main_dict = {}
    self.input_repos = []
    self.output_repos = []

  def ParseFile(self):
    f = open(self.filename)
    self.main_dict = eval(f.read())
    self.CreateReposFromDict(self.main_dict)
    f.close()
    return [self.input_repos, self.output_repos]

  def CreateReposFromDict(self, main_dict):
    for key, val in main_dict.items():
      repo_list = val
      for repo_dict in repo_list:
        repo = self.CreateRepoFromDict(repo_dict)
        if key == "input":
          self.input_repos.append(repo)
        elif key == "output":
          self.output_repos.append(repo)
        else:
          logger.GetLogger().LogFatal("Unknown key: %s found" % key)

  def GetDictValue(self, dictionary, key):
    if key in dictionary:
      return dictionary[key]
    else:
      return None

  def CreateRepoFromDict(self, repo_dict):
    repo_type = self.GetDictValue(repo_dict, "type")
    repo_address = self.GetDictValue(repo_dict, "address")
    repo_mappings = self.GetDictValue(repo_dict, "mappings")
    repo_ignores = self.GetDictValue(repo_dict, "ignores")
    repo_branch = self.GetDictValue(repo_dict, "branch")

    if repo_type == "p4":
      repo = P4Repo(repo_address,
                    repo_mappings)
    elif repo_type == "svn":
      repo = SvnRepo(repo_address,
                     repo_mappings)
    elif repo_type == "git":
      repo = GitRepo(repo_address,
                     repo_branch,
                     mappings=repo_mappings,
                     ignores=repo_ignores)
    else:
      logger.GetLogger().LogFatal("Unknown repo type: %s" % repo_type)
    return repo


@logger.HandleUncaughtExceptions
def Main(argv):
  parser = optparse.OptionParser()
  parser.add_option("-i",
                    "--input_file",
                    dest="input_file",
                    help="The input file that contains repo descriptions.")

  parser.add_option("-n",
                    "--dry_run",
                    dest="dry_run",
                    action="store_true",
                    default=False,
                    help="Do a dry run of the push.")

  options = parser.parse_args(argv)[0]
  if not options.input_file:
    parser.print_help()
    return 1
  rr = RepoReader(options.input_file)
  [input_repos, output_repos] = rr.ParseFile()

  for output_repo in output_repos:
    ret = output_repo.SetupForPush()
    if ret: return ret

  input_revisions = []
  for input_repo in input_repos:
    ret = input_repo.PullSources()
    if ret: return ret
    input_revisions.append(input_repo.revision)

  for input_repo in input_repos:
    for output_repo in output_repos:
      ret = input_repo.MapSources(output_repo.GetRoot())
      if ret: return ret

  commit_message = "Sync'd repos to: %s" % ",".join(input_revisions)
  for output_repo in output_repos:
    ret = output_repo.PushSources(commit_message, dry_run=options.dry_run)
    if ret: return ret

  if not options.dry_run:
    for output_repo in output_repos:
      output_repo.CleanupRoot()
    

  return ret


if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
