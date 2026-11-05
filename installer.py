# language: python, file: installer.py — приветствие, старт сразу
import tkinter as tk


class Installer:
    def __init__(self, root, on_installed):
        self.on_installed = on_installed
        self.win = tk.Toplevel(root)
        self.win.title("CS&SOFT")
        self.win.geometry("520x360+%d+%d" % (
            (root.winfo_screenwidth() - 520) // 2,
            (root.winfo_screenheight() - 360) // 2))
        self.win.resizable(False, False)
        self.win.configure(bg="#121212")
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        tk.Label(self.win, text="CS&SOFT", fg="#00ff88", bg="#121212",
                 font=("Segoe UI", 22, "bold")).pack(pady=(24, 8))
        tk.Label(self.win, text="Здравствуйте! Это чит CS&SOFT.",
                 fg="#cccccc", bg="#121212", font=("Segoe UI", 11)).pack(pady=(0, 4))
        tk.Label(self.win, text="Для открытия чита нажмите Insert.",
                 fg="#888888", bg="#121212", font=("Segoe UI", 10)).pack(pady=(0, 16))

        self.status = tk.Label(self.win, text="Нажмите «Продолжить», чтобы запустить.",
                               fg="#ffff00", bg="#121212", font=("Segoe UI", 10))
        self.status.pack(pady=(10, 10))

        self.button = tk.Button(self.win, text="Продолжить",
                                command=self.on_continue,
                                bg="#00ff88", fg="#121212",
                                font=("Segoe UI", 11, "bold"),
                                width=20, height=2, bd=0,
                                activebackground="#00cc66")
        self.button.pack(pady=10)

        self.progress = tk.Label(self.win, text="", fg="#888888", bg="#121212",
                                 font=("Segoe UI", 9))
        self.progress.pack(pady=(10, 0))

    def on_continue(self):
        self.button.config(state="disabled", text="Запуск...")
        self.status.config(text="Чит запущен!", fg="#00ff88")
        self.progress.config(text="Нажмите Insert в игре.")
        self.button.config(state="normal", text="Закрыть", command=self.close)
        self.on_installed()

    def close(self):
        self.win.destroy()
