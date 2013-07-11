"""A reproducing entity.

Part of the Chrome build flags optimization.

The Task class is used by different modules. Each module fills in the
corresponding information into a Task instance. Class Task contains the bit set
representing the flags selection. The builder module is responsible for filling
the image and the checksum field of a Task. The executor module will put the
execution output to the execution field.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'


class Task(object):
  """A single reproducing entity.

  A single test of performance with a particular set of flags. It records the
  flag set, the image, the check sum of the image and the cost.
  """

  def __init__(self, flag_set):
    """Set up the optimization flag selection for this task.

    Args:
      flag_set: the optimization flag set that is encapsulated by this task.
    """
    self._flag_set = flag_set

  def ReproduceWith(self, other):
    """Create a new SolutionCandidate by reproduction with another.

    Mix two Tasks together to form a new Task of the same class. This is one of
    the core functions of a GA.

    Args:
      other: The other Task to reproduce with.

    Returns: A Task that is a mix between self and other.
    """
    pass

  def Compile(self):
    """Run a compile.

    This method compile an image using the present flags, get the image,
    test the existent of the image and gathers monitoring information, and sets
    the internal cost (fitness) for this set of flags.
    """
    pass

  def GetFlags(self):
    pass

  def SetFlags(self, flags):
    pass

  def GetChecksum(self):
    pass

  def SetChecksum(self, checksum):
    pass

  def GetImage(self):
    pass

  def SetImage(self, image):
    pass
