from machine_pools import MachinePool

class MachinePoolFilter:
  def FilterPool(self, machine_pool):
    return machine_pool


class LightestLoadFilter(MachinePoolFilter):
  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool:
      machine.UpdateDynamicInfo()

    sorted_list = sorted(machine_pool, key=lambda m: m.load)
    ret.AddMachine(sorted_list[0])
    return ret


class ChromeOSFilter(MachinePoolFilter):
  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.os == "chromeos":
        ret.AddMachine(machine)
    return ret


class LinuxFilter(MachinePoolFilter):
  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.os == "linux":
        ret.AddMachine(machine)
    return ret

class UnlockedFilter(MachinePoolFilter):
  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.locked == False:
        ret.AddMachine(machine)
    return ret

class NameFilter(MachinePoolFilter):
  def __init__(self, name):
    self.name = name


  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.name == self.name:
        ret.AddMachine(machine)
    return ret


class NameListFilter(MachinePoolFilter):
  def __init__(self, names):
    self.names = []
    for name in names:
      self.names.append(name)

  def FilterPool(self, machine_pool):
    taken_list = self.names[:]
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.name in self.names:
        index = taken_list.index(machine.name)
        taken_list.remove(machine.name)
        ret.AddMachine(machine)
    if ret.Size() != len(self.names):
      print "Could not find: "
      print taken_list
      raise Exception("Could not find machines")
    return ret
