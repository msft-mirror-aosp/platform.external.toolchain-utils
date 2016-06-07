#!/usr/bin/python2
"""The binary search wrapper."""

from __future__ import print_function

import argparse
import os
import pickle
import sys
import tempfile

# Programtically adding utils python path to PYTHONPATH
if os.path.isabs(sys.argv[0]):
  utils_pythonpath = os.path.abspath('{0}/..'.format(os.path.dirname(sys.argv[
      0])))
else:
  wdir = os.getcwd()
  utils_pythonpath = os.path.abspath('{0}/{1}/..'.format(wdir, os.path.dirname(
      sys.argv[0])))
sys.path.append(utils_pythonpath)
# Now we do import from utils
from utils import command_executer
from utils import logger

import binary_search_perforce

STATE_FILE = '%s.state' % sys.argv[0]


class BinarySearchState(object):
  """The binary search state class."""

  def __init__(self, get_initial_items, switch_to_good, switch_to_bad,
               install_script, test_script, incremental, prune, iterations,
               prune_iterations, verify_level, file_args):
    self.get_initial_items = get_initial_items
    self.switch_to_good = switch_to_good
    self.switch_to_bad = switch_to_bad
    self.install_script = install_script
    self.test_script = test_script
    self.incremental = incremental
    self.prune = prune
    self.iterations = iterations
    self.prune_iterations = prune_iterations
    self.verify_level = verify_level
    self.file_args = file_args

    self.l = logger.GetLogger()
    self.ce = command_executer.GetCommandExecuter()

    self.bs = None
    self.all_items = None
    self.PopulateItemsUsingCommand(self.get_initial_items)
    self.currently_good_items = set([])
    self.currently_bad_items = set([])

  def SwitchToGood(self, item_list):
    if self.incremental:
      self.l.LogOutput('Incremental set. Wanted to switch %s to good' %
                       str(item_list))
      incremental_items = [
          item for item in item_list if item not in self.currently_good_items
      ]
      item_list = incremental_items
      self.l.LogOutput('Incremental set. Actually switching %s to good' %
                       str(item_list))

    if not item_list:
      return

    self.l.LogOutput('Switching %s to good' % str(item_list))
    self.RunSwitchScript(self.switch_to_good, item_list)
    self.currently_good_items = self.currently_good_items.union(set(item_list))
    self.currently_bad_items.difference_update(set(item_list))

  def SwitchToBad(self, item_list):
    if self.incremental:
      self.l.LogOutput('Incremental set. Wanted to switch %s to bad' %
                       str(item_list))
      incremental_items = [
          item for item in item_list if item not in self.currently_bad_items
      ]
      item_list = incremental_items
      self.l.LogOutput('Incremental set. Actually switching %s to bad' %
                       str(item_list))

    if not item_list:
      return

    self.l.LogOutput('Switching %s to bad' % str(item_list))
    self.RunSwitchScript(self.switch_to_bad, item_list)
    self.currently_bad_items = self.currently_bad_items.union(set(item_list))
    self.currently_good_items.difference_update(set(item_list))

  def RunSwitchScript(self, switch_script, item_list):
    if self.file_args:
      temp_file = tempfile.mktemp()
      f = open(temp_file, 'wb')
      f.write('\n'.join(item_list))
      f.close()
      command = '%s %s' % (switch_script, temp_file)
    else:
      command = '%s %s' % (switch_script, ' '.join(item_list))
    ret = self.ce.RunCommand(command)
    assert ret == 0, 'Switch script %s returned %d' % (switch_script, ret)

  def TestScript(self):
    command = self.test_script
    return self.ce.RunCommand(command)

  def InstallScript(self):
    if not self.install_script:
      return 0

    command = self.install_script
    return self.ce.RunCommand(command)

  def DoVerify(self):
    for _ in range(int(self.verify_level)):
      self.l.LogOutput('Resetting all items to good to verify.')
      self.SwitchToGood(self.all_items)
      status = self.InstallScript()
      assert status == 0, 'When reset_to_good, install should succeed.'
      status = self.TestScript()
      assert status == 0, 'When reset_to_good, status should be 0.'

      self.l.LogOutput('Resetting all items to bad to verify.')
      self.SwitchToBad(self.all_items)
      status = self.InstallScript()
      assert status == 0, 'When reset_to_bad, install should succeed.'
      status = self.TestScript()
      assert status == 1, 'When reset_to_bad, status should be 1.'

  def DoSearch(self):
    num_bad_items_history = []
    i = 0
    while True and len(self.all_items) > 1 and i < self.prune_iterations:
      i += 1
      terminated = self.DoBinarySearch()
      if not terminated:
        break
      if not self.prune:
        self.l.LogOutput('Not continuning further, --prune is not set')
        break
      # Prune is set.
      prune_index = self.bs.current

      if prune_index == len(self.all_items) - 1:
        self.l.LogOutput('First bad item is the last item. Breaking.')
        self.l.LogOutput('Only bad item is: %s' % self.all_items[-1])
        break

      num_bad_items = len(self.all_items) - prune_index
      num_bad_items_history.append(num_bad_items)

      if (num_bad_items_history[-num_bad_items:] ==
          [num_bad_items for _ in range(num_bad_items)]):
        self.l.LogOutput('num_bad_items_history: %s for past %d iterations. '
                         'Breaking.' % (str(num_bad_items_history),
                                        num_bad_items))
        self.l.LogOutput('Bad items are: %s' %
                         ' '.join(self.all_items[prune_index:]))
        break

      new_all_items = list(self.all_items)
      # Move prune item to the end of the list.
      new_all_items.append(new_all_items.pop(prune_index))

      if prune_index:
        new_all_items = new_all_items[prune_index - 1:]

      self.l.LogOutput('Old list: %s. New list: %s' % (str(self.all_items),
                                                       str(new_all_items)))

      # FIXME: Do we need to Convert the currently good items to bad
      self.PopulateItemsUsingList(new_all_items)

  def DoBinarySearch(self):
    i = 0
    terminated = False
    while i < self.iterations and not terminated:
      i += 1
      [bad_items, good_items] = self.GetNextItems()

      # TODO: bad_items should come first.
      self.SwitchToGood(good_items)
      self.SwitchToBad(bad_items)
      status = self.InstallScript()
      if status == 0:
        status = self.TestScript()
      else:
        # Install script failed, treat as skipped item
        status = 2
      terminated = self.bs.SetStatus(status)

      if terminated:
        self.l.LogOutput('Terminated!')
    if not terminated:
      self.l.LogOutput('Ran out of iterations searching...')
    self.l.LogOutput(str(self))
    return terminated

  def PopulateItemsUsingCommand(self, command):
    ce = command_executer.GetCommandExecuter()
    _, out, _ = ce.RunCommandWOutput(command)
    all_items = out.split()
    self.PopulateItemsUsingList(all_items)

  def PopulateItemsUsingList(self, all_items):
    self.all_items = all_items
    self.bs = binary_search_perforce.BinarySearcher()
    self.bs.SetSortedList(self.all_items)

  def SaveState(self):
    self.l = None
    self.ce = None
    # TODO Implement save/restore
    ###    return
    f = open(STATE_FILE, 'wb')
    pickle.dump(self, f)
    f.close()

  @classmethod
  def LoadState(cls):
    if not os.path.isfile(STATE_FILE):
      return None
    return pickle.load(file(STATE_FILE))

  def GetNextItems(self):
    border_item = self.bs.GetNext()
    index = self.all_items.index(border_item)

    next_bad_items = self.all_items[:index + 1]
    next_good_items = self.all_items[index + 1:]

    return [next_bad_items, next_good_items]

  def __str__(self):
    ret = ''
    ret += 'all: %s\n' % str(self.all_items)
    ret += 'currently_good: %s\n' % str(self.currently_good_items)
    ret += 'currently_bad: %s\n' % str(self.currently_bad_items)
    ret += str(self.bs)
    return ret


def _CanonicalizeScript(script_name):
  script_name = os.path.expanduser(script_name)
  if not script_name.startswith('/'):
    return os.path.join('.', script_name)


def Main(argv):
  """The main function."""
  # Common initializations

  parser = argparse.ArgumentParser()
  parser.add_argument('-n',
                      '--iterations',
                      dest='iterations',
                      help='Number of iterations to try in the search.',
                      default=50)
  parser.add_argument('-i',
                      '--get_initial_items',
                      dest='get_initial_items',
                      help='Script to run to get the initial objects.')
  parser.add_argument('-g',
                      '--switch_to_good',
                      dest='switch_to_good',
                      help='Script to run to switch to good.')
  parser.add_argument('-b',
                      '--switch_to_bad',
                      dest='switch_to_bad',
                      help='Script to run to switch to bad.')
  parser.add_argument('-I',
                      '--install_script',
                      dest='install_script',
                      default=None,
                      help=('Optional script to perform building, flashing, '
                            'and other setup before the test script runs.'))
  parser.add_argument('-t',
                      '--test_script',
                      dest='test_script',
                      help=('Script to run to test the '
                            'output after packages are built.'))
  parser.add_argument('-p',
                      '--prune',
                      dest='prune',
                      action='store_true',
                      default=False,
                      help=('Script to run to test the output after '
                            'packages are built.'))
  parser.add_argument('-c',
                      '--noincremental',
                      dest='noincremental',
                      action='store_true',
                      default=False,
                      help='Do not propagate good/bad changes incrementally.')
  parser.add_argument('-f',
                      '--file_args',
                      dest='file_args',
                      action='store_true',
                      default=False,
                      help='Use a file to pass arguments to scripts.')
  parser.add_argument('-v',
                      '--verify_level',
                      dest='verify_level',
                      default=1,
                      help=('Check binary search assumptions N times '
                            'before starting.'))
  parser.add_argument('-N',
                      '--prune_iterations',
                      dest='prune_iterations',
                      help='Number of prune iterations to try in the search.',
                      default=100)

  logger.GetLogger().LogOutput(' '.join(argv))
  options = parser.parse_args(argv)

  if not (options.get_initial_items and options.switch_to_good and
          options.switch_to_bad and options.test_script):
    parser.print_help()
    return 1

  iterations = int(options.iterations)
  switch_to_good = _CanonicalizeScript(options.switch_to_good)
  switch_to_bad = _CanonicalizeScript(options.switch_to_bad)
  install_script = options.install_script
  if install_script:
    install_script = _CanonicalizeScript(options.install_script)
  test_script = _CanonicalizeScript(options.test_script)
  get_initial_items = _CanonicalizeScript(options.get_initial_items)
  prune = options.prune
  prune_iterations = options.prune_iterations
  verify_level = options.verify_level
  file_args = options.file_args

  if options.noincremental:
    incremental = False
  else:
    incremental = True

  try:
    bss = BinarySearchState(get_initial_items, switch_to_good, switch_to_bad,
                            install_script, test_script, incremental, prune,
                            iterations, prune_iterations, verify_level,
                            file_args)
    bss.DoVerify()
    bss.DoSearch()

  except (KeyboardInterrupt, SystemExit):
    print('C-c pressed')
    bss.SaveState()
  return 0


if __name__ == '__main__':
  sys.exit(Main(sys.argv[1:]))
