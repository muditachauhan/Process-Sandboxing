# sandbox/process_control.py
import psutil
import os

# Windows-friendly priority map (psutil constants)
WINDOWS_PRIORITIES = {
    "Idle": psutil.IDLE_PRIORITY_CLASS,
    "Below Normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
    "Normal": psutil.NORMAL_PRIORITY_CLASS,
    "Above Normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
    "High": psutil.HIGH_PRIORITY_CLASS,
    "Realtime": psutil.REALTIME_PRIORITY_CLASS,
}

class ProcessControl:
    def __init__(self):
        self.psproc = None

    def set_process(self, psproc):
        self.psproc = psproc

    def clear_process(self):
        self.psproc = None

    def set_priority(self, level_name):
        if not self.psproc:
            raise RuntimeError("No process attached")
        if os.name == "nt":
            val = WINDOWS_PRIORITIES.get(level_name, None)
            if val is None:
                raise ValueError("Unknown priority")
            self.psproc.nice(val)
        else:
            # on POSIX, map to nice values
            mapping = {
                "Idle": 19, "Below Normal": 10, "Normal": 0,
                "Above Normal": -5, "High": -10, "Realtime": -20
            }
            self.psproc.nice(mapping.get(level_name, 0))

    def set_affinity(self, cores):
        if not self.psproc:
            raise RuntimeError("No process attached")
        try:
            self.psproc.cpu_affinity(cores)
        except AttributeError:
            # not supported on some systems
            raise RuntimeError("Setting affinity is not supported on this OS")
