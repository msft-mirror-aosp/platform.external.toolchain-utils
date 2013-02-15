class MachineDescription:
  def __init__(self, name, os, lock_required):
    self.name = name
    self.os = os
    self.lock_required = lock_required

  def SetLockRequired(self, lock_required):
    self.lock_required = lock_required

  def IsLockRequired(self):
    return self.lock_required

  def IsMatch(self, machine):
    if machine.locked == True:
      return False
    if self.name and machine.name == self.name:
      return True
    if self.os and machine.os == self.os:
      return True
