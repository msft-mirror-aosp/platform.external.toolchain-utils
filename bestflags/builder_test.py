"""Builder unittest."""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import unittest

import builder


class BuilderTest(unittest.TestCase):
  """This class test the Builder.

  Given the same flags set, the image and the cost should result the same from
  the builder.
  """

  def setUp(self):
    """Create the Builder to be tested."""

    self.builder = builder.Builder(1, None)

  def testCompile(self):
    """"Test the build method.

    Call the build method twice, and test the results. The results should be the
    same, i.e., the image, the cost and the checksum should be the same.
    Either the compile method or the set_compile_result of the input Generation
    for the Builder should be called, but not both.
    """
    self.builder.build(self)

  def testInit(self):
    """"Test the init method.

    If a certain flag set has been encountered before, the builder should not
    recompile the image with the same optimization flag set.
    """

    pass

if __name__ == '__main__':
  unittest.main()
