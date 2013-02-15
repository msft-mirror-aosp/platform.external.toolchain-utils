STATUS_NOT_EXECUTED = 0
STATUS_EXECUTING = 1
STATUS_COMPLETED = 2

class Job:

  def __init__(self):
    self.status = STATUS_NOT_EXECUTED
    self.dependencies = []

  def SetStatus(self, status):
    self.status = status

  def GetStatus(self):
    return self.status

  def AddDependency(self, dep):
    self.dependencies.append(dep)

  def GetDependencies(self):
    return self.dependencies

  def GetNumDependencies(self):
    return len(self.GetDependencies())

  def IsReady(self):
    # If we have already started executing, we aren't ready
    if self.GetStatus() != STATUS_NOT_EXECUTED:
      return False

    # Check that all our dependencies have been executed
    for dependency in self.GetDependencies():
      if dependency.GetStatus() != STATUS_COMPLETED:
        return False

    return True
