"""Builder unittest.

This module tests the build helper method and the worker method.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import multiprocessing
import random
import sys
import unittest

import builder
import pipeline_process


def MockTaskCostGenerator():
  """Calls a random number generator and returns a negative number."""
  return random.randint(-sys.maxint - 1, -1)


class MockTask(object):
  """This class emulates an actual task.

  It does not do the actual compile, but simply returns the build result as when
  this task is constructed.
  """

  def __init__(self, flags, cost):
    """Set up the compile results for this task.

    Args:
      flags: the optimization flags of this task.
      cost: the mork build cost of this task.

      The _pre_cost field stored the 'compiled' cost. Once this task is
      compiled, i.e., by calling the compile method , the _cost field will have
      this 'compiled' cost.
    """

    self._flags = flags
    self._pre_cost = cost

  def get_flags(self):
    return self._flags

  def __eq__(self, other):
    if isinstance(other, MockTask):
      return self._flags == other._flags and self._cost == other._cost
    return False

  def set_build_result(self, cost):
    self._cost = cost

  def compile(self):
    self._cost = self._pre_cost

  def get_build_result(self):
    return self._cost

  def compiled(self):
    """Indicates whether the task has been compiled."""

    return '_cost' in self.__dict__


class BuilderTest(unittest.TestCase):
  """This class tests the Builder.

  Given the same flags set, the image and the cost should result the same from
  the builder.
  """

  def testHelper(self):
    """"Test the build helper.

    Call the build method twice, and test the results. The results should be the
    same, i.e., the cost should be the same.
    """

    # Set up the input, helper and output queue for the worker method.
    manager = multiprocessing.Manager()
    helper_queue = manager.Queue()
    output_queue = manager.Queue()
    built_queue = manager.Queue()

    # Set up the helper process that holds the helper method.
    helper_process = multiprocessing.Process(target=builder.build_helper,
                                             args=({}, helper_queue,
                                                   built_queue, output_queue))
    helper_process.start()

    # A dictionary defines the mock compile result to the build_helper.
    mock_compile_result = {1: 1995, 2: 59, 9: 1027}

    # Test if there is a task that is done before, whether the duplicate task
    # will have the same result. Here, two different scenarios are tested. That
    # is the mock results are added to the built_queue before and after the
    # corresponding mock tasks being ;added to the input queue.
    built_queue.put((9, mock_compile_result[9]))

    # The output of the helper should contain all the following tasks.
    results = [1, 1, 2, 9]

    # Testing the correctness of having tasks having the same flags key, here 1.
    for result in results:
      helper_queue.put(MockTask(result, MockTaskCostGenerator()))

    built_queue.put((2, mock_compile_result[2]))
    built_queue.put((1, mock_compile_result[1]))

    # Signal there is no more duplicate task.
    helper_queue.put(pipeline_process.POISONPILL)
    helper_process.join()

    while results:
      task = output_queue.get()
      flags = task._flags
      cost = task._cost
      self.assertTrue(flags in results)
      if flags in mock_compile_result:
        self.assertTrue(cost, mock_compile_result[flags])
      results.remove(task._flags)

  def testWorker(self):
    """"Test the actual build worker method.

    The worker should process all the input tasks and output the tasks to the
    helper and result queue.
    """

    manager = multiprocessing.Manager()
    output_queue = manager.Queue()
    built_queue = manager.Queue()

    # A dictionary defines the mock tasks and their corresponding compile
    # results.
    mock_compile_tasks = {1: 86, 2: 788}

    mock_tasks = []

    for flag, cost in mock_compile_tasks.iteritems():
      mock_tasks.append(MockTask(flag, cost))

    # Submit the mock tasks to the build worker.
    for mock_task in mock_tasks:
      builder.build_worker(mock_task, built_queue, output_queue)

    # The tasks, from the output queue, should be the same as the input and
    # should be compiled.
    for task in mock_tasks:
      output = output_queue.get()
      self.assertEqual(output, task)
      self.assertTrue(output.compiled())

    # The tasks, from the built queue, should be defined in the
    # mock_compile_tasks dictionary.
    for flag, cost in mock_compile_tasks.iteritems():
      helper_input = built_queue.get()
      self.assertEqual(helper_input, (flag, cost))


if __name__ == '__main__':
  unittest.main()
