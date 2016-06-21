#!/usr/bin/python2
"""The unified package/object bisecting tool."""

from __future__ import print_function

import abc
import argparse
import os
import sys

if os.path.isabs(sys.argv[0]):
  utils_pythonpath = os.path.abspath('{0}/..'.format(os.path.dirname(sys.argv[
      0])))
else:
  wdir = os.getcwd()
  utils_pythonpath = os.path.abspath('{0}/{1}/..'.format(wdir, os.path.dirname(
      sys.argv[0])))
sys.path.append(utils_pythonpath)
from utils import command_executer
from utils import logger

import binary_search_state


class Bisector(object):
  """The abstract base class for Bisectors."""

  # Make Bisector an abstract class
  __metaclass__ = abc.ABCMeta

  def __init__(self, options):
    self.options = options
    self.logger = logger.GetLogger()
    self.ce = command_executer.GetCommandExecuter()

  @abc.abstractmethod
  def PreRun(self):
    pass

  @abc.abstractmethod
  def Run(self):
    pass

  @abc.abstractmethod
  def PostRun(self):
    pass


class BisectPackage(Bisector):
  """The class for package bisection steps."""

  cros_pkg_setup = './cros_pkg_setup.sh'
  cros_pkg_cleanup = './cros_pkg_%s_cleanup.sh'
  default_kwargs = {
      'get_initial_items': './cros_pkg_get_initial_items.sh',
      'switch_to_good': './cros_pkg_switch_to_good.sh',
      'switch_to_bad': './cros_pkg_switch_to_bad.sh',
      'install_script': './cros_pkg_install.sh',
      'test_script': './cros_pkg_interactive_test.sh',
      'noincremental': False,
      'prune': True,
      'file_args': True
  }

  def __init__(self, options):
    super(BisectPackage, self).__init__(options)

  def PreRun(self):
    os.chdir('./cros_pkg')
    cmd = ('%s %s %s' %
           (self.cros_pkg_setup, self.options.board, self.options.remote))
    ret, _, _ = self.ce.RunCommandWExceptionCleanup(cmd, print_to_console=True)
    if ret:
      self.logger.LogError('Package bisector setup failed w/ error %d' % ret)
      return 1
    return 0

  def Run(self):
    return binary_search_state.Run(**self.default_kwargs)

  def PostRun(self):
    cmd = self.cros_pkg_cleanup % self.options.board
    ret, _, _ = self.ce.RunCommandWExceptionCleanup(cmd, print_to_console=True)
    if ret:
      self.logger.LogError('Package bisector cleanup failed w/ error %d' % ret)
      return 1
    return 0


class BisectObject(Bisector):
  """The class for object bisection steps."""

  def __init__(self, options):
    super(BisectObject, self).__init__(options)

  def PreRun(self):
    raise NotImplementedError('Object bisecting still WIP')

  def Run(self):
    return 1

  def PostRun(self):
    return 1


def Run(bisector):
  ret = bisector.PreRun()
  if ret:
    return ret

  ret = bisector.Run()
  if ret:
    return ret

  ret = bisector.PostRun()
  if ret:
    return ret

  return 0


def Main(argv):
  parser = argparse.ArgumentParser(epilog=('Run ./bisect.py {command} --help '
                                           'for individual subcommand '
                                           'help/args.'))
  subparsers = parser.add_subparsers(title='Bisect mode',
                                     description=('Whether to package or object'
                                                  'bisect'))

  parser_package = subparsers.add_parser('package')
  parser_package.add_argument('board', help='Board to target')
  parser_package.add_argument('remote', help='Remote machine to test on')
  parser_package.set_defaults(handler=BisectPackage)

  parser_object = subparsers.add_parser('object')
  parser_object.set_defaults(handler=BisectObject)

  options = parser.parse_args(argv)

  subcmd = options.handler
  del options.handler

  bisector = subcmd(options)
  return Run(bisector)


if __name__ == '__main__':
  sys.exit(Main(sys.argv[1:]))
