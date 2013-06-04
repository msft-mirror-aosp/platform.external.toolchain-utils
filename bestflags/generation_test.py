"""Generation unittest."""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import unittest

import generation


class GenerationTest(unittest.TestCase):
  """This class test the Generation class.

  A generation class should not produce a task that has been generated before.
  The task returned as the best task should really be the best.

  Given two generations, if the second one has improved upon the first one,
  the result method should return true and false otherwise.
  """

  def setUp(self):
    pass

  def testNext(self):
    """"Test the next method.

    Call the next method n times and all the tasks in each generation should be
    unique.
    """
    pass

  def testImprove(self):
    """"Test the improve method.

    If the successor generation has improvement upon the parent generation, the
    result from the improve method should indicate so.
    """

    pass

if __name__ == '__main__':
  unittest.main()
