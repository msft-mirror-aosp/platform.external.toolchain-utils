#!/usr/bin/python2
"""The unified package/object bisecting tool."""

from __future__ import print_function

import abc
import argparse
import sys
from argparse import RawTextHelpFormatter

import common

from utils import command_executer
from utils import logger

import binary_search_state


class Bisector(object):
  """The abstract base class for Bisectors."""

  # Make Bisector an abstract class
  __metaclass__ = abc.ABCMeta

  def __init__(self, options, overrides=None):
    """Constructor for Bisector abstract base class

    Args:
      options: positional arguments for specific mode (board, remote, etc.)
      overrides: optional dict of overrides for argument defaults
    """
    self.options = options
    self.overrides = overrides
    if not overrides:
      self.overrides = {}
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

  cros_pkg_setup = 'cros_pkg/setup.sh'
  cros_pkg_cleanup = 'cros_pkg/%s_cleanup.sh'

  def __init__(self, options, overrides):
    super(BisectPackage, self).__init__(options, overrides)
    self.default_kwargs = {
        'get_initial_items': 'cros_pkg/get_initial_items.sh',
        'switch_to_good': 'cros_pkg/switch_to_good.sh',
        'switch_to_bad': 'cros_pkg/switch_to_bad.sh',
        'install_script': 'cros_pkg/install.sh',
        'test_script': 'cros_pkg/interactive_test.sh',
        'noincremental': False,
        'prune': True,
        'file_args': True
    }

  def PreRun(self):
    cmd = ('%s %s %s' %
           (self.cros_pkg_setup, self.options.board, self.options.remote))
    ret, _, _ = self.ce.RunCommandWExceptionCleanup(cmd, print_to_console=True)
    if ret:
      self.logger.LogError('Package bisector setup failed w/ error %d' % ret)
      return 1
    return 0

  def Run(self):
    self.default_kwargs.update(self.overrides)
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

  def __init__(self, options, overrides):
    super(BisectObject, self).__init__(options, overrides)

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


_HELP_EPILOG = """
Run ./bisect.py {method} --help for individual method help/args

------------------

See README.bisect for examples on argument overriding

See below for full override argument reference:
"""


def Main(argv):
  override_parser = argparse.ArgumentParser(add_help=False,
                                            argument_default=argparse.SUPPRESS,
                                            usage='bisect.py {mode} [options]')
  common.BuildArgParser(override_parser, override=True)

  epilog = _HELP_EPILOG + override_parser.format_help()
  parser = argparse.ArgumentParser(epilog=epilog,
                                   formatter_class=RawTextHelpFormatter)
  subparsers = parser.add_subparsers(title='Bisect mode',
                                     description=('Which bisection method to '
                                                  'use. Each method has '
                                                  'specific setup and '
                                                  'arguments. Please consult '
                                                  'the README for more '
                                                  'information.'))

  parser_package = subparsers.add_parser('package')
  parser_package.add_argument('board', help='Board to target')
  parser_package.add_argument('remote', help='Remote machine to test on')
  parser_package.set_defaults(handler=BisectPackage)

  parser_object = subparsers.add_parser('object')
  parser_object.set_defaults(handler=BisectObject)

  options, remaining = parser.parse_known_args(argv)
  if remaining:
    overrides = override_parser.parse_args(remaining)
    overrides = vars(overrides)
  else:
    overrides = {}

  subcmd = options.handler
  del options.handler

  bisector = subcmd(options, overrides)
  return Run(bisector)


if __name__ == '__main__':
  os.chdir(os.path.dirname(__file__))
  sys.exit(Main(sys.argv[1:]))
