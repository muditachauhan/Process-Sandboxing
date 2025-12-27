# gui/app_gui.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import psutil
import os
import threading
import time
import matplotlib
matplotlib.use("Agg")  # for PNG rendering offscreen
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from sandbox.sandbox_core import Sandbox
from sandbox.resource_monitor import ResourceMonitor
from sandbox.restriction_manager import RestrictionManager
from sandbox.process_control import ProcessControl
from utils.pdf_exporter import export_report_pdf

class SandboxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Process Sandboxing - Final Phase")
        self.root.geometry("980x680")
        self.root.configure(bg="#f0f0f0")

        # subsystems
        self.restrict = RestrictionManager()
        self.sandbox = Sandbox(self.append_output)
        self.monitor = ResourceMonitor(self.system_callback, self.process_callback, poll_interval=1.0)
        self.proc_control = ProcessControl()

        # data
        self.proc_psutil = None
        self.proc_cmd = ""
        self.proc_pid = None
        self.proc_priority = "Below Normal"
        self.proc_affinity = []

        # UI
        self._build_ui()
        self._chart_data_init()
        # start monitor (it will not call process_callback until attached)
        self.monitor.start()
        # start chart updater loop
        self._start_chart_thread()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="Command / File:").grid(row=0, column=0, sticky="w")
        self.cmd_var = tk.StringVar()
        self.entry_cmd = ttk.Entry(top, textvariable=self.cmd_var, width=70)
        self.entry_cmd.grid(row=0, column=1, columnspan=4, padx=6, sticky="w")
        ttk.Button(top, text="Browse", command=self.browse_file).grid(row=0, column=5, padx=6)
        ttk.Button(top, text="Run", command=self.run_cmd).grid(row=0, column=6, padx=6)
        ttk.Button(top, text="Attach by PID", command=self.attach_by_pid).grid(row=0, column=7, padx=6)

        # left: details + controls
        left = ttk.LabelFrame(self.root, text="Process", padding=8)
        left.place(x=10, y=70, width=460, height=380)

        ttk.Label(left, text="PID:").grid(row=0, column=0, sticky="w")
        self.pid_var = tk.StringVar(value="N/A")
        ttk.Label(left, textvariable=self.pid_var).grid(row=0, column=1, sticky="w")

        ttk.Label(left, text="Status:").grid(row=1, column=0, sticky="w")
        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(left, textvariable=self.status_var).grid(row=1, column=1, sticky="w")

        ttk.Label(left, text="CPU %:").grid(row=2, column=0, sticky="w")
        self.cpu_var = tk.StringVar(value="0.0%")
        ttk.Label(left, textvariable=self.cpu_var).grid(row=2, column=1, sticky="w")

        ttk.Label(left, text="Memory %:").grid(row=3, column=0, sticky="w")
        self.mem_var = tk.StringVar(value="0.0%")
        ttk.Label(left, textvariable=self.mem_var).grid(row=3, column=1, sticky="w")

        ttk.Label(left, text="RSS:").grid(row=4, column=0, sticky="w")
        self.rss_var = tk.StringVar(value="0 B")
        ttk.Label(left, textvariable=self.rss_var).grid(row=4, column=1, sticky="w")

        # Controls like screenshot: Priority + affinity checkboxes + apply/kill buttons
        ctrl = ttk.LabelFrame(left, text="Controls", padding=8)
        ctrl.grid(row=6, column=0, columnspan=3, pady=8, sticky="w")

        ttk.Label(ctrl, text="Priority:").grid(row=0, column=0, sticky="w")
        self.priority_combo = ttk.Combobox(ctrl, values=list(self._priority_list()), state="readonly", width=16)
        self.priority_combo.set("Below Normal")
        self.priority_combo.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Button(ctrl, text="Apply", command=self.apply_priority).grid(row=0, column=2, padx=6)

        ttk.Label(ctrl, text="Affinity:").grid(row=1, column=0, sticky="nw")
        self.aff_frame = ttk.Frame(ctrl)
        self.aff_frame.grid(row=1, column=1, columnspan=2, sticky="w")
        self._build_affinity_checkboxes()

        ttk.Button(ctrl, text="Apply Affinity", command=self.apply_affinity).grid(row=2, column=1, pady=6)
        ttk.Button(ctrl, text="Kill Process", command=self.kill_proc).grid(row=2, column=2, pady=6)

        # right side: chart + network toggle + export pdf + log
        right = ttk.LabelFrame(self.root, text="Live & Actions", padding=8)
        right.place(x=480, y=70, width=480, height=560)

        # chart area (matplotlib)
        self.fig, self.ax = plt.subplots(figsize=(5,2.2), dpi=100)
        self.ax.set_ylim(0,100)
        self.ax.set_ylabel("Usage %")
        self.ax.set_xlabel("samples")
        self.line_cpu, = self.ax.plot([], [], label="CPU")
        self.line_mem, = self.ax.plot([], [], label="Memory")
        self.ax.legend()
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(padx=4, pady=4)

        # network toggle
        net_frame = ttk.Frame(right)
        net_frame.pack(pady=6)
        self.net_label_var = tk.StringVar(value="Network: Blocked")
        ttk.Label(net_frame, textvariable=self.net_label_var).pack(side="left", padx=6)
        ttk.Button(net_frame, text="Toggle Network", command=self.toggle_network).pack(side="left", padx=6)

        # export PDF button
        pdf_frame = ttk.Frame(right)
        pdf_frame.pack(pady=6)
        ttk.Button(pdf_frame, text="Export Report to PDF", command=self.export_pdf).pack()

        # log textbox
        log_frame = ttk.LabelFrame(right, text="Log")
        log_frame.pack(fill="both", expand=True, padx=4, pady=6)
        self.log_text = tk.Text(log_frame, height=12)
        self.log_text.pack(fill="both", expand=True)

    def _priority_list(self):
        return ["Idle", "Below Normal", "Normal", "Above Normal", "High", "Realtime"]

    def _build_affinity_checkboxes(self):
        # clear any existing
        for w in self.aff_frame.winfo_children():
            w.destroy()
        self.core_vars = []
        total = psutil.cpu_count(logical=True) or 1
        cols = 8
        for i in range(total):
            v = tk.IntVar(value=1)
            cb = ttk.Checkbutton(self.aff_frame, text=str(i), variable=v)
            cb.grid(row=i//cols, column=i%cols, sticky="w", padx=2, pady=1)
            self.core_vars.append(v)

    # ---------- command / attach ----------
    def browse_file(self):
        path = filedialog.askopenfilename(title="Select script or executable",
                                          filetypes=[("Python Files", "*.py"), ("Executables", "*.exe"), ("All files", "*.*")])
        if path:
            # if python file, create command; if exe, run exe directly
            if path.lower().endswith(".py"):
                self.cmd_var.set(f'python "{path}"')
            else:
                self.cmd_var.set(f'"{path}"')

    def run_cmd(self):
        cmd = self.cmd_var.get().strip()
        if not cmd:
            messagebox.showwarning("No command", "Enter or select a command to run.")
            return
        self.append_output(f"[Running] {cmd}")
        self.proc_cmd = cmd
        self.sandbox.run_command(cmd)
        # small delay to pick up process - we read sandbox.current_log to find pid; safer: attach by pid manually
        time.sleep(0.2)
        # user should use Attach by PID for process-specific control (we leave attach explicit)
        self.status_var.set("Running (launched)")

    def attach_by_pid(self):
        ans = simpledialog.askinteger("Attach by PID", "Enter PID to attach:")
        if not ans:
            return
        try:
            p = psutil.Process(ans)
            self.proc_psutil = p
            self.proc_pid = p.pid
            self.proc_control.set_process(p)
            self.monitor.attach_process(p)
            self.pid_var.set(str(self.proc_pid))
            self.append_output(f"[Attached] PID {self.proc_pid} ({p.name()})")
            self.status_var.set("Attached")
        except Exception as e:
            messagebox.showerror("Attach failed", str(e))

    # ---------- Process controls ----------
    def apply_priority(self):
        level = self.priority_combo.get()
        if not self.proc_psutil:
            messagebox.showwarning("No process", "Attach to a process (Attach by PID) first to set priority.")
            return
        try:
            self.proc_control.set_priority(level)
            self.proc_priority = level
            self.append_output(f"[Priority] set to {level}")
        except Exception as e:
            messagebox.showerror("Priority error", str(e))

    def apply_affinity(self):
        cores = [i for i, v in enumerate(self.core_vars) if v.get() == 1]
        if not self.proc_psutil:
            messagebox.showwarning("No process", "Attach to a process (Attach by PID) first to set affinity.")
            return
        try:
            self.proc_control.set_affinity(cores)
            self.proc_affinity = cores
            self.append_output(f"[Affinity] set to {cores}")
        except Exception as e:
            messagebox.showerror("Affinity error", str(e))

    def kill_proc(self):
        if not self.proc_psutil:
            messagebox.showwarning("No process", "Attach to a process (Attach by PID) first to kill.")
            return
        try:
            self.proc_psutil.terminate()
            self.append_output("[Killed] process terminated.")
            self.status_var.set("Terminated")
        except Exception as e:
            messagebox.showerror("Kill failed", str(e))

    # ---------- monitor callbacks ----------
    def system_callback(self, cpu, mem):
        # update small status labels for system usage if needed
        # not displayed directly in main UI aside from chart
        pass

    def process_callback(self, proc_cpu, proc_mem):
        self.cpu_var.set(f"{proc_cpu:.1f}%")
        self.mem_var.set(f"{proc_mem:.1f}%")
        try:
            if self.proc_psutil:
                rss = self.proc_psutil.memory_info().rss
                self.rss_var.set(f"{rss//1024} KB")
        except Exception:
            pass

    # ---------- output log ----------
    def append_output(self, text):
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {text}\n")
        self.log_text.see("end")

    # ---------- chart logic ----------
    def _chart_data_init(self):
        self.chart_cpu = []
        self.chart_mem = []

    def _start_chart_thread(self):
        def loop():
            while True:
                # append latest system metrics
                try:
                    cpu = psutil.cpu_percent(interval=0.5)
                    mem = psutil.virtual_memory().percent
                except Exception:
                    cpu, mem = 0.0, 0.0
                self.chart_cpu.append(cpu)
                self.chart_mem.append(mem)
                if len(self.chart_cpu) > 60:
                    self.chart_cpu.pop(0); self.chart_mem.pop(0)
                # update plot on main thread via after
                self.root.after(0, self._update_plot)
                time.sleep(1)
        threading.Thread(target=loop, daemon=True).start()

    def _update_plot(self):
        xs = list(range(len(self.chart_cpu)))
        self.line_cpu.set_data(xs, self.chart_cpu)
        self.line_mem.set_data(xs, self.chart_mem)
        if len(xs) == 0:
            return
        self.ax.set_xlim(0, max(30, len(xs)))
        self.ax.set_ylim(0, max(100, max(self.chart_cpu + [0])))
        self.canvas.draw_idle()

    # ---------- network toggle ----------
    def toggle_network(self):
        status = self.restrict.toggle_network()
        self.restrict.simulate_network_block()
        self.net_label_var.set(f"Network: {'Blocked' if status else 'Allowed'}")
        self.append_output(f"[Network] {'Blocked' if status else 'Allowed'}")

    # ---------- export to PDF ----------
    def export_pdf(self):
        # create small chart image first
        chart_img = os.path.join("reports", "chart.png")
        os.makedirs("reports", exist_ok=True)
        try:
            # save chart as PNG
            fig2, ax2 = plt.subplots(figsize=(6,2), dpi=150)
            ax2.plot(self.chart_cpu, label="CPU")
            ax2.plot(self.chart_mem, label="Memory")
            ax2.set_ylim(0, 100)
            ax2.legend()
            ax2.set_title("System Usage History")
            fig2.tight_layout()
            fig2.savefig(chart_img)
            fig2.clf()
            plt.close(fig2)
        except Exception as e:
            self.append_output(f"[Export] chart save failed: {e}")
            chart_img = None

        # prepare metadata & logs
        metadata = {
            "PID": str(self.proc_pid or "N/A"),
            "Command": self.proc_cmd or "N/A",
            "Priority": self.proc_priority,
            "Affinity": str(self.proc_affinity),
        }
        log_text = self.log_text.get("1.0", "end").strip()
        pdf_name = f"reports/sandbox_report_{int(time.time())}.pdf"
        try:
            export_report_pdf(pdf_name, metadata, log_text, chart_img)
            self.append_output(f"[Export] PDF saved: {pdf_name}")
            messagebox.showinfo("Exported", f"Report exported to {pdf_name}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

