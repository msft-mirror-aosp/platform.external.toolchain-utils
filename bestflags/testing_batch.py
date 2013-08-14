# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Hill climbing unitest.

Part of the Chrome build flags optimization.

Test the variations of the hill climbing algorithms.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import multiprocessing
import random
import sys
import unittest

import flags
from flags import Flag
from flags import FlagSet
from genetic_algorithm import GAGeneration
from genetic_algorithm import GATask
from hill_climb_best_neighbor import HillClimbingBestBranch
import pipeline_process
from steering import Steering
from task import BUILD_STAGE
from task import Task
from task import TEST_STAGE


# The number of flags be tested.
NUM_FLAGS = 5

# The value range of the flags.
FLAG_RANGES = 10

# The following variables are meta data for the Genetic Algorithm.
STOP_THRESHOLD = 20
NUM_CHROMOSOMES = 10
NUM_TRIALS = 20
MUTATION_RATE = 0.03


def _GenerateRandomRasks(specs):
  """Generate a task that has random values.

  Args:
    specs: A list of spec from which the flag set is created.

  Returns:
    A set containing a task that has random values.
  """

  flag_set = []

  for spec in specs:
    numeric_flag_match = flags.Search(spec)
    if numeric_flag_match:
      # Numeric flags.
      start = int(numeric_flag_match.group('start'))
      end = int(numeric_flag_match.group('end'))

      value = random.randint(start - 1, end - 1)
      if value != start - 1:
        # If the value falls in the range, this flag is enabled.
        flag_set.append(Flag(spec, value))
    else:
      # Boolean flags.
      if random.randint(0, 1):
        flag_set.append(Flag(spec))

  return set([Task(FlagSet(flag_set))])


def _GenerateAllFlagsTasks(specs):
  """Generate a task that all the flags are enable.

  All the boolean flags in the specs will be enabled and all the numeric flag
  with have the largest legal value.

  Args:
    specs: A list of spec from which the flag set is created.

  Returns:
    A set containing a task that has all flags enabled.
  """

  flag_set = []

  for spec in specs:
    numeric_flag_match = flags.Search(spec)

    if numeric_flag_match:
      value = (int(numeric_flag_match.group('end')) - 1)
    else:
      value = -1
    flag_set.append(Flag(spec, value))

  return set([Task(FlagSet(flag_set))])


def _GenerateNoFlagTask():
  return set([Task(FlagSet([]))])


def _GenerateRandomGATasks(specs, num_tasks, num_trials):
  """Generate a set of tasks for the Genetic Algorithm.

  Args:
    specs: A list of spec from which the flag set is created.
    num_tasks: number of tasks that should be generated.
    num_trials: the maximum number of tries should be attempted to generate the
      set of tasks.

  Returns:
    A set of randomly generated tasks.
  """

  tasks = set([])

  total_trials = 0
  while len(tasks) < num_tasks and total_trials < num_trials:
    new_flag = FlagSet([Flag(spec) for spec in specs if random.randint(0, 1)])
    new_task = GATask(new_flag)

    if new_task in tasks:
      total_trials += 1
    else:
      tasks.add(new_task)
      total_trials = 0

  return tasks


def _ComputeCost(cost_func, specs, flag_set):
  """Compute the mock cost of the flag_set using the input cost function.

  All the boolean flags in the specs will be enabled and all the numeric flag
  with have the largest legal value.

  Args:
    cost_func: The cost function which is used to compute the mock cost of a
      dictionary of flags.
    specs: All the specs that are used in the algorithm. This is used to check
      whether certain flag is disabled in the flag_set dictionary.
    flag_set: a dictionary of the spec and flag pairs.

  Returns:
    The mock cost of the input dictionary of the flags.
  """

  values = []

  for spec in specs:
    # If a flag is enabled, its value is added. Otherwise a padding 0 is added.
    values.append(flag_set[spec].GetValue() if spec in flag_set else 0)

  # The cost function string can use the values array.
  return eval(cost_func)


def _GenerateTestFlags(num_flags, upper_bound, file_name):
  """Generate a set of mock flags and write it to a configuration file.

  Generate a set of mock flags

  Args:
    num_flags: Number of numeric flags to be generated.
    upper_bound: The value of the upper bound of the range.
    file_name: The configuration file name into which the mock flags are put.
  """

  with open(file_name, 'w') as output_file:
    num_flags = int(num_flags)
    upper_bound = int(upper_bound)
    for i in range(num_flags):
      output_file.write('%s=[1-%d]\n' % (i, upper_bound))


def _TestAlgorithm(cost_func, specs, generations, best_result):
  """Test the best result the algorithm should return.

  Set up the framework, run the input algorithm and verify the result.

  Args:
    cost_func: The cost function which is used to compute the mock cost of a
      dictionary of flags.
    specs: All the specs that are used in the algorithm. This is used to check
      whether certain flag is disabled in the flag_set dictionary.
    generations: The initial generations to be evaluated.
    best_result: The expected best result of the algorithm. If best_result is
      -1, the algorithm may or may not return the best value. Therefore, no
      assertion will be inserted.
  """

  # Set up the utilities to test the framework.
  manager = multiprocessing.Manager()
  input_queue = manager.Queue()
  output_queue = manager.Queue()
  pp_steer = multiprocessing.Process(target=Steering,
                                     args=(set(), generations, output_queue,
                                           input_queue))
  pp_steer.start()

  # The best result of the algorithm so far.
  result = sys.maxint

  while True:
    task = input_queue.get()

    # POISONPILL signal the ends of the algorithm.
    if task == pipeline_process.POISONPILL:
      break

    task.SetResult(BUILD_STAGE, (0, 0, 0, 0, 0))

    # Compute the mock cost for the task.
    task_result = _ComputeCost(cost_func, specs, task.GetFlags())
    task.SetResult(TEST_STAGE, task_result)

    # If the mock result of the current task is the best so far, set this
    # result to be the best result.
    if task_result < result:
      result = task_result

    output_queue.put(task)

  pp_steer.join()

  # Only do this test when best_result is not -1.
  if best_result != -1:
    assert best_result == result


class FlagAlgorithms(unittest.TestCase):
  """This class test the FlagSet class."""

  def testBestHillClimb(self):
    """Test the best hill climb algorithm.

    Test whether it finds the best results as expected.
    """

    # Initiate the build/test command and the log directory.
    Task.InitLogCommand(None, None, 'output')

    # Generate the testing specs.
    mock_test_file = 'scale_mock_test'
    _GenerateTestFlags(NUM_FLAGS, FLAG_RANGES, mock_test_file)
    specs = flags.ReadConf(mock_test_file)

    # Generate the initial generations for a test whose cost function is the
    # summation of the values of all the flags.
    generation_tasks = _GenerateAllFlagsTasks(specs)
    generations = [HillClimbingBestBranch(generation_tasks, set([]), specs)]

    # Test the algorithm. The cost function is the summation of all the values
    # of all the flags. Therefore, the best value is supposed to be 0, i.e.,
    # when all the flags are disabled.
    _TestAlgorithm('sum(values[0:len(values)])', specs, generations, 0)

    # This test uses a cost function that is the negative of the previous cost
    # function. Therefore, the best result should be found in task with all the
    # flags enabled.
    cost_function = 'sys.maxint - sum(values[0:len(values)])'
    all_flags = list(generation_tasks)[0].GetFlags()
    cost = _ComputeCost(cost_function, specs, all_flags)

    # Generate the initial generations.
    generation_tasks = _GenerateNoFlagTask()
    generations = [HillClimbingBestBranch(generation_tasks, set([]), specs)]

    # Test the algorithm. The cost function is negative of the summation of all
    # the values of all the flags. Therefore, the best value is supposed to be
    # 0, i.e., when all the flags are disabled.
    _TestAlgorithm(cost_function, specs, generations, cost)

  def testGeneticAlgorithm(self):
    """Test the Genetic Algorithm.

    Do a function testing here and see how well it scales.
    """

    # Initiate the build/test command and the log directory.
    Task.InitLogCommand(None, None, 'output')

    # Generate the testing specs.
    mock_test_file = 'scale_mock_test'
    _GenerateTestFlags(NUM_FLAGS, FLAG_RANGES, mock_test_file)
    specs = flags.ReadConf(mock_test_file)

    # Initiate the build/test command and the log directory.
    GAGeneration.InitMetaData(STOP_THRESHOLD, NUM_CHROMOSOMES, NUM_TRIALS,
                              specs, MUTATION_RATE)

    # Generate the initial generations.
    generation_tasks = _GenerateRandomGATasks(specs, NUM_CHROMOSOMES,
                                              NUM_TRIALS)
    generations = [GAGeneration(generation_tasks, set([]), 0)]

    # Test the algorithm.
    _TestAlgorithm('sum(values[0:len(values)])', specs, generations, -1)
    cost_func = 'sys.maxint - sum(values[0:len(values)])'
    _TestAlgorithm(cost_func, specs, generations, -1)


if __name__ == '__main__':
  unittest.main()
