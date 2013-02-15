#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

__author__ = 'kbaclawski@google.com (Krystian Baclawski)'

import collections
import os.path

from automation.common import command as cmd


class PathMapping(object):
  """Stores information about relative path mapping (remote to local)."""

  @classmethod
  def ListFromPathDict(cls, prefix_path_dict):
    """Takes {'prefix1': ['path1',...], ...} and returns a list of mappings."""

    mappings = []

    for prefix, paths in sorted(prefix_path_dict.items()):
      for path in sorted(paths):
        mappings.append(cls(os.path.join(prefix, path)))

    return mappings

  def __init__(self, remote, local=None):
    self.remote = remote

    if not local:
      self.local = remote

  @staticmethod
  def _FixPath(path_s):
    parts = [part for part in path_s.strip('/').split('/') if part]

    return os.path.join(*parts)

  def _GetRemote(self):
    return self._remote

  def _SetRemote(self, path_s):
    self._remote = self._FixPath(path_s)

  remote = property(_GetRemote, _SetRemote)

  def _GetLocal(self):
    return self._local

  def _SetLocal(self, path_s):
    self._local = self._FixPath(path_s)

  local = property(_GetLocal, _SetLocal)

  def GetAbsolute(self, depot, client):
    return (os.path.join('//', depot, self.remote),
            os.path.join('//', client, self.local))

  def __str__(self):
    return '%s(%s => %s)' % (self.__class__.__name__, self.remote, self.local)


class View(collections.MutableSet):
  """Keeps all information about local client required to work with perforce."""

  def __init__(self, depot, mappings=None, client=None):
    self.depot = depot

    if client:
      self.client = client

    self._mappings = set(mappings or [])

  @staticmethod
  def _FixRoot(root_s):
    parts = root_s.strip('/').split('/', 1)

    if len(parts) != 1:
      return None

    return parts[0]

  def _GetDepot(self):
    return self._depot

  def _SetDepot(self, depot_s):
    depot = self._FixRoot(depot_s)
    assert depot, 'Not a valid depot name: "%s".' % depot_s
    self._depot = depot

  depot = property(_GetDepot, _SetDepot)

  def _GetClient(self):
    return self._client

  def _SetClient(self, client_s):
    client = self._FixRoot(client_s)
    assert client, 'Not a valid client name: "%s".' % client_s
    self._client = client

  client = property(_GetClient, _SetClient)

  def add(self, mapping):
    assert type(mapping) is PathMapping
    self._mappings.add(mapping)

  def discard(self, mapping):
    assert type(mapping) is PathMapping
    self._mappings.discard(mapping)

  def __contains__(self, value):
    return value in self._mappings

  def __len__(self):
    return len(self._mappings)

  def __iter__(self):
    return iter(mapping.GetAbsolute(self.depot, self.client)
                for mapping in self._mappings)


class CommandsFactory(object):
  """Creates shell commands used for interaction with Perforce."""

  def __init__(self, checkout_dir, p4view, name=None, port=None):
    self.port = port or 'perforce2:2666'
    self.view = p4view
    self.view.client = name or 'p4-automation-$HOSTNAME-$JOB_ID'
    self.checkout_dir = checkout_dir
    self.p4config_path = os.path.join(self.checkout_dir, '.p4config')

  def Setup(self):
    return cmd.Chain(
        'mkdir -p %s' % self.checkout_dir,
        'cp ${HOME}/.p4config %s' % self.checkout_dir,
        'chmod u+w %s' % self.p4config_path,
        'echo "P4PORT=%s" >> %s' % (self.port, self.p4config_path),
        'echo "P4CLIENT=%s" >> %s' % (self.view.client, self.p4config_path))

  def Create(self):
    # TODO(kbaclawski): Could we support value list for options consistently?
    mappings = ['-a \"%s %s\"' % mapping for mapping in self.view]

    return cmd.Shell('g4', 'client', *mappings)

  def Sync(self):
    return cmd.Shell('g4', 'sync', '...')

  def Remove(self):
    return cmd.Shell('g4', 'client', '-d', self.view.client)
