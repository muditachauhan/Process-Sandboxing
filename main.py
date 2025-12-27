# main.py
import tkinter as tk
from gui.app_gui import SandboxApp

def main():
    root = tk.Tk()
    app = SandboxApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
