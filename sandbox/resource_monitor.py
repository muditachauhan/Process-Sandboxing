# sandbox/resource_monitor.py
import psutil
import threading
import time

class ResourceMonitor:
    """
    Polls system CPU & memory, and if attached to a psutil.Process,
    polls process CPU% / memory% too via provided callbacks.
    """
    def __init__(self, system_callback, process_callback=None, poll_interval=1.0):
        self.system_callback = system_callback      # called with (cpu_percent, mem_percent)
        self.process_callback = process_callback    # called with (proc_cpu, proc_mem)
        self.poll_interval = poll_interval
        self._running = False
        self._psproc = None

    def attach_process(self, psproc):
        self._psproc = psproc

    def detach_process(self):
        self._psproc = None

    def start(self):
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            if self.system_callback:
                self.system_callback(cpu, mem)
            if self._psproc:
                try:
                    # cpu_percent with interval=0.1 to get instant-ish value
                    proc_cpu = self._psproc.cpu_percent(interval=0.1)
                    proc_mem = self._psproc.memory_percent()
                except Exception:
                    proc_cpu, proc_mem = 0.0, 0.0
                if self.process_callback:
                    self.process_callback(proc_cpu, proc_mem)
            time.sleep(self.poll_interval)

