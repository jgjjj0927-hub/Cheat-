# language: python, file: main.py — root, события, трей
import sys
import tkinter as tk
import queue

import win32api
import pystray
from PIL import Image, ImageDraw

import cheat
from installer import Installer
from overlay import Overlay


def make_tray_icon():
    img = Image.new("RGB", (64, 64), "#121212")
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), outline="#00ff88", width=4)
    d.text((24, 22), "C", fill="#00ff88")
    return img


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.overlay = Overlay(self.root)
        self.installer = None
        self.tray = None
        self.installed = False
        self.events = queue.Queue()
        self._insert_held = False
        self.root.after(50, self._poll_events)

    def _poll_events(self):
        try:
            if win32api.GetAsyncKeyState(0x2D) & 0x8000:
                if not self._insert_held:
                    self.events.put("toggle")
                    self._insert_held = True
            else:
                self._insert_held = False
        except Exception:
            pass

        try:
            while True:
                ev = self.events.get_nowait()
                if ev == "toggle" and self.installed:
                    self.overlay.toggle_menu()
                elif ev == "quit":
                    self._quit()
                    return
        except queue.Empty:
            pass
        self.root.after(50, self._poll_events)

    def start(self):
        self.installer = Installer(self.root, self._on_installed)
        self.overlay.update()
        self.root.mainloop()

    def _on_installed(self):
        self.installed = True
        cheat.start_cheat()
        self._start_tray()

    def _start_tray(self):
        self.tray = pystray.Icon(
            "CS&SOFT", make_tray_icon(), "CS&SOFT",
            menu=pystray.Menu(
                pystray.MenuItem("Open menu",
                                 lambda i, it: self.events.put("toggle")),
                pystray.MenuItem("Exit",
                                 lambda i, it: self.events.put("quit")),
            ))
        self.tray.run_detached()

    def _quit(self):
        try:
            if self.tray:
                self.tray.stop()
        except Exception:
            pass
        self.root.quit()
        self.root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    App().start()
