import sys
import threading
import time
from image_checksummer import ImageChecksummer
import image_chromeos
import lock_machine
from utils import command_executer
from utils import logger
from utils.file_utils import FileUtils

CHECKSUM_FILE = "/usr/local/osimage_checksum_file"


class CrosMachine(object):
  def __init__(self, name):
    self.name = name
    self.image = None
    self.checksum = None
    self.locked = False
    self.released_time = time.time()
    self.autotest_run = None

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
    self.no_lock = False
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
      self.num_reimages += 1
      if retval:
        raise Exception("Could not image machine: '%s'." % machine.name)
      machine.checksum = checksum
      machine.image = chromeos_image

    return retval

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
      self._all_machines.append(CrosMachine(machine_name))

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

      if not self._machines:
        machine_names = []
        for machine in self._all_machines:
          machine_names.append(machine.name)
        raise Exception("Could not acquire any of the following machines: '%s'"
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
          autotest_status = m.autotest_run.status
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
