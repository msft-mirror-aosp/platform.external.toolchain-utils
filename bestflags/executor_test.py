"""Tester unittest."""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import unittest

import executor


class TesterTest(unittest.TestCase):
  """This class test the Executor.

  Given the same flags set and/or checksum, the image and the cost should be the
  same from the Executor.
  """

  def setUp(self):
    """Create the Executor to be tested."""

    self.tester = executor.Tester(1, None)

  def testExecute(self):
    """"Test the execute method.

    Call the execute method twice, and test the results. The results should be
    the same, i.e., the cost should be the same.
    Either the execute method or the set_execution_result of the input
    Generation for the Tester should be called, but not both.
    """
    self.tester.execute(self)

  def testInit(self):
    """"Test the init method.

    If a certain checksum has been encountered before, the Tester should not
    reexecute the images with the same checksum.
    """

    pass

if __name__ == '__main__':
  unittest.main()
