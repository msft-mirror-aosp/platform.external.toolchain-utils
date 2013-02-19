import hashlib
import image_chromeos
import lock_machine
import math
import os.path
import sys
import threading
import time
from image_checksummer import ImageChecksummer
from utils import command_executer
from utils import logger
from utils.file_utils import FileUtils

CHECKSUM_FILE = "/usr/local/osimage_checksum_file"


class CrosMachine(object):
  def __init__(self, name, chromeos_root):
    self.name = name
    self.image = None
    self.checksum = None
    self.locked = False
    self.released_time = time.time()
    self.autotest_run = None
    self.chromeos_root = chromeos_root
    self._GetMemoryInfo()
    self._GetCPUInfo()
    self._ComputeMachineChecksumString()
    self._ComputeMachineChecksum()

  def _ParseMemoryInfo(self):
    line = self.meminfo.splitlines()[0]
    usable_kbytes = int(line.split()[1])
    # This code is from src/third_party/autotest/files/client/bin/base_utils.py
    # usable_kbytes is system's usable DRAM in kbytes,
    #   as reported by memtotal() from device /proc/meminfo memtotal
    #   after Linux deducts 1.5% to 9.5% for system table overhead
    # Undo the unknown actual deduction by rounding up
    #   to next small multiple of a big power-of-two
    #   eg  12GB - 5.1% gets rounded back up to 12GB
    mindeduct = 0.005  # 0.5 percent
    maxdeduct = 0.095  # 9.5 percent
    # deduction range 1.5% .. 9.5% supports physical mem sizes
    #    6GB .. 12GB in steps of .5GB
    #   12GB .. 24GB in steps of 1 GB
    #   24GB .. 48GB in steps of 2 GB ...
    # Finer granularity in physical mem sizes would require
    #   tighter spread between min and max possible deductions

    # increase mem size by at least min deduction, without rounding
    min_kbytes = int(usable_kbytes / (1.0 - mindeduct))
    # increase mem size further by 2**n rounding, by 0..roundKb or more
    round_kbytes = int(usable_kbytes / (1.0 - maxdeduct)) - min_kbytes
    # find least binary roundup 2**n that covers worst-cast roundKb
    mod2n = 1 << int(math.ceil(math.log(round_kbytes, 2)))
    # have round_kbytes <= mod2n < round_kbytes*2
    # round min_kbytes up to next multiple of mod2n
    phys_kbytes = min_kbytes + mod2n - 1
    phys_kbytes -= phys_kbytes % mod2n  # clear low bits
    self.phys_kbytes = phys_kbytes

  def _GetMemoryInfo(self):
    #TODO yunlian: when the machine in rebooting, it will not return 
    #meminfo, the assert does not catch it either
    ce = command_executer.GetCommandExecuter()
    command = "cat /proc/meminfo"
    ret, self.meminfo, _ = ce.CrosRunCommand(
        command, return_output=True,
        machine=self.name, username="root", chromeos_root=self.chromeos_root)
    assert ret == 0, "Could not get meminfo from machine: %s" % self.name
    if ret == 0:
      self._ParseMemoryInfo()

  #cpuinfo format is different across architecture
  #need to find a better way to parse it.
  def _ParseCPUInfo(self,cpuinfo):
    return 0

  def _GetCPUInfo(self):
    ce = command_executer.GetCommandExecuter()
    command = "cat /proc/cpuinfo"
    ret, self.cpuinfo, _ = ce.CrosRunCommand(
        command, return_output=True,
        machine=self.name, username="root", chromeos_root=self.chromeos_root)
    assert ret == 0, "Could not get cpuinfo from machine: %s" % self.name
    if ret == 0:
      self._ParseCPUInfo(self.cpuinfo)

  def _ComputeMachineChecksumString(self):
    self.checksum_string = ""
    exclude_lines_list = ["MHz", "BogoMIPS", "bogomips"]
    for line in self.cpuinfo.splitlines():
      if not any([e in line for e in exclude_lines_list]):
        self.checksum_string += line
    self.checksum_string += " " + str(self.phys_kbytes)

  def _ComputeMachineChecksum(self):
    if self.checksum_string:
      self.machine_checksum = hashlib.md5(self.checksum_string).hexdigest()
    else:
      self.machine_checksum = ""

  def __str__(self):
    l = []
    l.append(self.name)
    l.append(str(self.image))
    l.append(str(self.checksum))
    l.append(str(self.locked))
    l.append(str(self.released_time))
    return ", ".join(l)


class MachineManager(object):
  def __init__(self, chromeos_root):
    self._lock = threading.RLock()
    self._all_machines = []
    self._machines = []
    self.image_lock = threading.Lock()
    self.num_reimages = 0
    self.chromeos_root = None
    if os.path.isdir(lock_machine.Machine.LOCKS_DIR):
      self.no_lock = False
    else:
      self.no_lock = True
    self.initialized = False
    self.chromeos_root = chromeos_root

  def ImageMachine(self, machine, chromeos_image, board=None):
    checksum = ImageChecksummer().Checksum(chromeos_image)
    if machine.checksum == checksum:
      return
    chromeos_root = FileUtils().ChromeOSRootFromImage(chromeos_image)
    if not chromeos_root:
      chromeos_root = self.chromeos_root
    image_args = [image_chromeos.__file__,
                  "--chromeos_root=%s" % chromeos_root,
                  "--image=%s" % chromeos_image,
                  "--remote=%s" % machine.name]
    if board:
      image_args.append("--board=%s" % board)

    # Currently can't image two machines at once.
    # So have to serialized on this lock.
    ce = command_executer.GetCommandExecuter()
    with self.image_lock:
      retval = ce.RunCommand(" ".join(["python"] + image_args))
      if retval:
        raise Exception("Could not image machine: '%s'." % machine.name)
      else:
        self.num_reimages += 1
      machine.checksum = checksum
      machine.image = chromeos_image

    return retval

  def ComputeCommonCheckSum(self):
    self.machine_checksum = ""
    for machine in self.GetMachines():
      if machine.machine_checksum:
        self.machine_checksum = machine.machine_checksum
        break

  def ComputeCommonCheckSumString(self):
    self.machine_checksum_string = ""
    for machine in self.GetMachines():
      if machine.checksum_string:
        self.machine_checksum_string = machine.checksum_string
        break

  def _TryToLockMachine(self, cros_machine):
    with self._lock:
      assert cros_machine, "Machine can't be None"
      for m in self._machines:
        assert m.name != cros_machine.name, (
            "Tried to double-lock %s" % cros_machine.name)
      if self.no_lock:
        locked = True
      else:
        locked = lock_machine.Machine(cros_machine.name).Lock(True, sys.argv[0])
      if locked:
        self._machines.append(cros_machine)
        ce = command_executer.GetCommandExecuter()
        command = "cat %s" % CHECKSUM_FILE
        ret, out, _ = ce.CrosRunCommand(
            command, return_output=True, chromeos_root=self.chromeos_root,
            machine=cros_machine.name)
        if ret == 0:
          cros_machine.checksum = out.strip()
      else:
        logger.GetLogger().LogOutput("Couldn't lock: %s" % cros_machine.name)

  # This is called from single threaded mode.
  def AddMachine(self, machine_name):
    with self._lock:
      for m in self._all_machines:
        assert m.name != machine_name, "Tried to double-add %s" % machine_name
      cm = CrosMachine(machine_name, self.chromeos_root)
      assert cm.machine_checksum, ("Could not find checksum for machine %s" %
                           machine_name)
      self._all_machines.append(cm)

  def AreAllMachineSame(self):
    checksums = [m.machine_checksum for m in self.GetMachines()]
    return len(set(checksums)) == 1

  def AcquireMachine(self, chromeos_image):
    image_checksum = ImageChecksummer().Checksum(chromeos_image)
    with self._lock:
      # Lazily external lock machines
      if not self.initialized:
        for m in self._all_machines:
          self._TryToLockMachine(m)
        self.initialized = True
        for m in self._all_machines:
          m.released_time = time.time()

      if not self.AreAllMachineSame():
        logger.GetLogger().LogFatal("-- not all the machine are identical")
      if not self._machines:
        machine_names = []
        for machine in self._all_machines:
          machine_names.append(machine.name)
        logger.GetLogger().LogFatal("Could not acquire any of the"
                                  "following machines: '%s'"
                                  % ", ".join(machine_names))

###      for m in self._machines:
###        if (m.locked and time.time() - m.released_time < 10 and
###            m.checksum == image_checksum):
###          return None
      for m in [machine for machine in self._machines if not machine.locked]:
        if m.checksum == image_checksum:
          m.locked = True
          m.autotest_run = threading.current_thread()
          return m
      for m in [machine for machine in self._machines if not machine.locked]:
        if not m.checksum:
          m.locked = True
          m.autotest_run = threading.current_thread()
          return m
      # This logic ensures that threads waiting on a machine will get a machine
      # with a checksum equal to their image over other threads. This saves time
      # when crosperf initially assigns the machines to threads by minimizing
      # the number of re-images.
      # TODO(asharif): If we centralize the thread-scheduler, we wont need this
      # code and can implement minimal reimaging code more cleanly.
      for m in [machine for machine in self._machines if not machine.locked]:
        if time.time() - m.released_time > 20:
          m.locked = True
          m.autotest_run = threading.current_thread()
          return m
    return None

  def GetMachines(self):
    return self._all_machines

  def ReleaseMachine(self, machine):
    with self._lock:
      for m in self._machines:
        if machine.name == m.name:
          assert m.locked == True, "Tried to double-release %s" % m.name
          m.released_time = time.time()
          m.locked = False
          m.status = "Available"
          break

  def Cleanup(self):
    with self._lock:
      # Unlock all machines.
      for m in self._machines:
        if not self.no_lock:
          res = lock_machine.Machine(m.name).Unlock(True)
          if not res:
            logger.GetLogger().LogError("Could not unlock machine: '%s'."
                                        % m.name)

  def __str__(self):
    with self._lock:
      l = ["MachineManager Status:"]
      for m in self._machines:
        l.append(str(m))
      return "\n".join(l)

  def AsString(self):
    with self._lock:
      stringify_fmt = "%-30s %-10s %-4s %-25s %-32s"
      header = stringify_fmt % ("Machine", "Thread", "Lock", "Status",
                                "Checksum")
      table = [header]
      for m in self._machines:
        if m.autotest_run:
          autotest_name = m.autotest_run.name
          autotest_status = m.autotest_run.timeline.GetLastEvent()
        else:
          autotest_name = ""
          autotest_status = ""

        try:
          machine_string = stringify_fmt % (m.name,
                                            autotest_name,
                                            m.locked,
                                            autotest_status,
                                            m.checksum)
        except Exception:
          machine_string = ""
        table.append(machine_string)
      return "Machine Status:\n%s" % "\n".join(table)


class MockMachineManager(object):
  def __init__(self):
    self.machines = []

  def ImageMachine(self, machine_name, chromeos_image, board=None):
    return 0

  def AddMachine(self, machine_name):
    self.machines.append(CrosMachine(machine_name))

  def AcquireMachine(self, chromeos_image):
    for machine in self.machines:
      if not machine.locked:
        machine.locked = True
        return machine
    return None

  def ReleaseMachine(self, machine):
    machine.locked = False

  def GetMachines(self):
    return self.machines
