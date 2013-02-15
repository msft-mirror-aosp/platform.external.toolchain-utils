class MachineDescription:
  def __init__(self, name, os, lock_required):
    self.name = name
    self.os = os
    self.lock_required = lock_required
    self.preferred_machines = []

  def SetLockRequired(self, lock_required):
    self.lock_required = lock_required

  def IsLockRequired(self):
    return self.lock_required

  def IsMatch(self, machine):
    if machine.locked == True:
      return False
    if self.name:
      if machine.name == self.name:
        return True
      else:
        return False
    if self.os:
      if machine.os == self.os:
        return True
      else:
        return False
    return False

  def GetPreferredMachines(self):
    return self.preferred_machines

  def AddPreferredMachine(self, name):
    self.preferred_machines.append(name)
