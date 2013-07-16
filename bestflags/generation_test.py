"""Generation unittest.

Part of the Chrome build flags optimization.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import random
import unittest

from generation import Generation
from mock_task import MockTask


# Pick an integer at random.
TESTSTAGE = -125

# The number of tasks to be put in a generation to be tested.
NUMTASKS = 20

# The stride of permutation used to shuffle the input list of tasks. Should be
# relatively prime with NUMTASKS.
STRIDE = 7


class GenerationMockTask(MockTask):
  """This class defines the mock task to test the Generation class.

  The task instances will be inserted into a set. Therefore the hash and the
  equal methods are overridden. The generation class considers the identifier to
  set the cost of the task in a set, thus the identifier is used in the
  overriding methods.
  """

  def __hash__(self):
    return self._identifier

  def __eq__(self, other):
    if isinstance(other, MockTask):
      return self._identifier == other.GetIdentifier(self._stage)
    return False


class GenerationTest(unittest.TestCase):
  """This class test the Generation class.

  Given a set of tasks in the generation, if there is any task that is pending,
  then the Done method will return false, and true otherwise.
  """

  def testDone(self):
    """"Test the Done method.

    Produce a generation with a set of tasks. Set the cost of the task one by
    one and verify that the Done method returns false before setting the cost
    for all the tasks. After the costs of all the tasks are set, the Done method
    should return true.
    """

    random.seed(0)

    testing_tasks = range(NUMTASKS)

    # The tasks for the generation to be tested.
    generation_tasks = [GenerationMockTask(TESTSTAGE, t) for t in testing_tasks]

    gen = Generation(set(generation_tasks), None)

    # Permute the list.
    permutation = [(t * STRIDE) % NUMTASKS for t in range(NUMTASKS)]
    permuted_tasks = [testing_tasks[index] for index in permutation]

    # The Done method of the Generation should return false before all the tasks
    # in the permuted list are set.
    for testing_task in permuted_tasks:
      assert not gen.Done()

      # Mark a task as done by calling the UpdateTask method of the generation.
      # Send the generation the task as well as its results.
      gen.UpdateTask(GenerationMockTask(TESTSTAGE, testing_task))

    # The Done method should return true after all the tasks in the permuted
    # list is set.
    assert gen.Done()

if __name__ == '__main__':
  unittest.main()
