# sandbox/sandbox_core.py
import subprocess
import threading
import tempfile
import os
import datetime

class Sandbox:
    """
    Runs a command inside a sandbox folder (temp directory).
    Logs stdout/stderr to a file and calls a callback for each output line.
    """
    def __init__(self, output_callback):
        self.process = None
        self.output_callback = output_callback
        self.sandbox_dir = os.path.join(tempfile.gettempdir(), "sandbox_env")
        os.makedirs(self.sandbox_dir, exist_ok=True)
        self.current_log_path = None

    def run_command(self, command):
        def target():
            try:
                # create reports folder and log file
                os.makedirs("reports", exist_ok=True)
                log_name = f"sandbox_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                self.current_log_path = os.path.join("reports", log_name)
                self.output_callback(f"[Sandbox Dir] {self.sandbox_dir}")
                with open(self.current_log_path, "w", encoding="utf-8") as logf:
                    # Launch process inside sandbox_dir
                    self.process = subprocess.Popen(
                        command,
                        cwd=self.sandbox_dir,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    # Read stdout line by line
                    for line in self.process.stdout:
                        if line is None:
                            break
                        line = line.rstrip("\n")
                        logf.write(line + "\n")
                        logf.flush()
                        self.output_callback(line)
                    # read remaining stderr
                    err = self.process.stderr.read()
                    if err:
                        for l in err.splitlines():
                            logf.write(l + "\n")
                            self.output_callback(f"ERR: {l}")
                    self.output_callback(f"[Log saved at] {self.current_log_path}")
            except Exception as ex:
                self.output_callback(f"[Sandbox error] {ex}")

        th = threading.Thread(target=target, daemon=True)
        th.start()

    def stop_process(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                return "Process terminated."
            except Exception as e:
                return f"Terminate failed: {e}"
        return "No process running."

    def get_current_log(self):
        return self.current_log_path
