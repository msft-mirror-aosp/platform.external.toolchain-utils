
class MachineDescription:
  def __init__(self, filters=[], lock_required=False):
    self.filters = filters
    self.lock_required = lock_required

  def AddFilter(self, filter):
    self.filters.append(filter)

  def GetFilters(self):
    return self.filters

  def __iter__(self):
    current = 0
    while current < len(self.filters):
      yield self.filters[current]
      current += 1

  def SetLockRequired(self, lock_required):
    self.lock_required = lock_required

  def IsLockRequired(self):
    return self.lock_required

