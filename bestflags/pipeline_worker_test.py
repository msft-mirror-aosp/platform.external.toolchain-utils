"""Unittest for the pipeline_worker functions in the build/test stage.

Part of the Chrome build flags optimization.

This module tests the helper method and the worker method.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import multiprocessing
import random
import sys
import unittest

import pipeline_process
import pipeline_worker


TESTSTAGE = 0


def MockTaskCostGenerator():
  """Calls a random number generator and returns a negative number."""
  return random.randint(-sys.maxint - 1, -1)


class MockTask(object):
  """This class emulates an actual task.

  It does not do the actual work, but simply returns the result as given when
  this task is constructed.
  """

  def __init__(self, identifier, cost):
    """Set up the results for this task.

    Args:
      identifier: the identifier of this task.
      cost: the mock cost of this task.

      The _pre_cost field stores the cost. Once this task is performed, i.e., by
      calling the work method , the _cost field will have this cost.
    """

    self._identifier = identifier
    self._pre_cost = cost

  def get_identifier(self, stage):
    assert stage == TESTSTAGE
    return self._identifier

  def __eq__(self, other):
    if isinstance(other, MockTask):
      return self._identifier == other._identifier and self._cost == other._cost
    return False

  def set_result(self, stage, cost):
    assert stage == TESTSTAGE
    self._cost = cost

  def work(self, stage):
    assert stage == TESTSTAGE
    self._cost = self._pre_cost

  def get_result(self, stage):
    assert stage == TESTSTAGE
    return self._cost

  def done(self, stage):
    """Indicates whether the task has been performed."""

    assert stage == TESTSTAGE
    return '_cost' in self.__dict__


class AuxiliaryTest(unittest.TestCase):
  """This class tests the pipeline_worker functions.

  Given the same identifier, the cost should result the same from the
  pipeline_worker functions.
  """

  def testHelper(self):
    """"Test the helper.

    Call the helper method twice, and test the results. The results should be
    the same, i.e., the cost should be the same.
    """

    # Set up the input, helper and output queue for the helper method.
    manager = multiprocessing.Manager()
    helper_queue = manager.Queue()
    result_queue = manager.Queue()
    completed_queue = manager.Queue()

    # Set up the helper process that holds the helper method.
    helper_process = multiprocessing.Process(target=pipeline_worker.helper,
                                             args=(TESTSTAGE, {}, helper_queue,
                                                   completed_queue,
                                                   result_queue))
    helper_process.start()

    # A dictionary defines the mock result to the helper.
    mock_result = {1: 1995, 2: 59, 9: 1027}

    # Test if there is a task that is done before, whether the duplicate task
    # will have the same result. Here, two different scenarios are tested. That
    # is the mock results are added to the completed_queue before and after the
    # corresponding mock tasks being added to the input queue.
    completed_queue.put((9, mock_result[9]))

    # The output of the helper should contain all the following tasks.
    results = [1, 1, 2, 9]

    # Testing the correctness of having tasks having the same identifier, here
    # 1.
    for result in results:
      helper_queue.put(MockTask(result, MockTaskCostGenerator()))

    completed_queue.put((2, mock_result[2]))
    completed_queue.put((1, mock_result[1]))

    # Signal there is no more duplicate task.
    helper_queue.put(pipeline_process.POISONPILL)
    helper_process.join()

    while results:
      task = result_queue.get()
      identifier = task._identifier
      cost = task._cost
      self.assertTrue(identifier in results)
      if identifier in mock_result:
        self.assertTrue(cost, mock_result[identifier])
      results.remove(task._identifier)

  def testWorker(self):
    """"Test the worker method.

    The worker should process all the input tasks and output the tasks to the
    helper and result queue.
    """

    manager = multiprocessing.Manager()
    result_queue = manager.Queue()
    completed_queue = manager.Queue()

    # A dictionary defines the mock tasks and their corresponding results.
    mock_work_tasks = {1: 86, 2: 788}

    mock_tasks = []

    for flag, cost in mock_work_tasks.iteritems():
      mock_tasks.append(MockTask(flag, cost))

    # Submit the mock tasks to the worker.
    for mock_task in mock_tasks:
      pipeline_worker.worker(TESTSTAGE, mock_task, completed_queue,
                             result_queue)

    # The tasks, from the output queue, should be the same as the input and
    # should be performed.
    for task in mock_tasks:
      output = result_queue.get()
      self.assertEqual(output, task)
      self.assertTrue(output.done(TESTSTAGE))

    # The tasks, from the completed_queue, should be defined in the
    # mock_work_tasks dictionary.
    for flag, cost in mock_work_tasks.iteritems():
      helper_input = completed_queue.get()
      self.assertEqual(helper_input, (flag, cost))


if __name__ == '__main__':
  unittest.main()
