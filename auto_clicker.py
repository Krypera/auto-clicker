#!/usr/bin/env python3
"""Auto Clicker — a simple, open-source, cross-platform auto clicker.

A minimal desktop tool written with Tkinter. It uses `pynput` as its only
dependency, for both mouse control and the global keyboard shortcut.

Usage:
    python auto_clicker.py

Default start/stop hotkey: F6
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from pynput import keyboard
from pynput.mouse import Button, Controller as MouseController


# Default global start/stop hotkey.
HOTKEY = keyboard.Key.f6
HOTKEY_LABEL = "F6"

# Smallest safe wait (seconds) so a 0 interval cannot freeze the system.
MIN_INTERVAL = 0.001


class ClickWorker(threading.Thread):
    """Runs the click loop on a separate thread so the GUI never blocks."""

    BUTTONS = {
        "Left": Button.left,
        "Right": Button.right,
        "Middle": Button.middle,
    }

    def __init__(self, interval, button, click_count, position,
                 repeat_limit, on_finish):
        super().__init__(daemon=True)
        self.interval = interval          # wait between clicks, in seconds
        self.button = button              # pynput.mouse.Button
        self.click_count = click_count    # 1 = single click, 2 = double click
        self.position = position          # None = cursor location, (x, y) = fixed
        self.repeat_limit = repeat_limit  # None = unlimited, int = N clicks
        self._on_finish = on_finish
        self._stop_event = threading.Event()
        self._mouse = MouseController()

    def stop(self):
        """Ask the loop to stop at its next check."""
        self._stop_event.set()

    def run(self):
        clicks_done = 0
        try:
            while not self._stop_event.is_set():
                if self.position is not None:
                    self._mouse.position = self.position
                self._mouse.click(self.button, self.click_count)
                clicks_done += 1

                if self.repeat_limit is not None and clicks_done >= self.repeat_limit:
                    break

                # Wait returns early if stop is requested (no busy-waiting).
                if self._stop_event.wait(self.interval):
                    break
        finally:
            if self._on_finish is not None:
                self._on_finish()


class AutoClickerApp:
    """Tkinter-based user interface and state management."""

    def __init__(self, root):
        self.root = root
        self.worker = None

        root.title("Auto Clicker")
        root.resizable(False, False)

        self._build_ui()
        self._start_hotkey_listener()

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self.root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")

        # --- Click interval ---
        interval_frame = ttk.LabelFrame(main, text="Click Interval")
        interval_frame.grid(row=0, column=0, sticky="ew", **pad)

        self.hours = tk.StringVar(value="0")
        self.minutes = tk.StringVar(value="0")
        self.seconds = tk.StringVar(value="0")
        self.millis = tk.StringVar(value="100")

        for col, (label, var, upper) in enumerate([
            ("Hours", self.hours, 99),
            ("Minutes", self.minutes, 59),
            ("Seconds", self.seconds, 59),
            ("Milliseconds", self.millis, 999),
        ]):
            ttk.Label(interval_frame, text=label).grid(row=0, column=col, padx=6)
            ttk.Spinbox(
                interval_frame, from_=0, to=upper, width=6,
                textvariable=var, justify="center",
            ).grid(row=1, column=col, padx=6, pady=(0, 6))

        # --- Click options ---
        options_frame = ttk.LabelFrame(main, text="Click Options")
        options_frame.grid(row=1, column=0, sticky="ew", **pad)

        ttk.Label(options_frame, text="Mouse button").grid(
            row=0, column=0, sticky="w", padx=6, pady=4)
        self.button_var = tk.StringVar(value="Left")
        ttk.Combobox(
            options_frame, textvariable=self.button_var, state="readonly",
            width=10, values=list(ClickWorker.BUTTONS.keys()),
        ).grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(options_frame, text="Click type").grid(
            row=0, column=2, sticky="w", padx=6, pady=4)
        self.click_type_var = tk.StringVar(value="Single")
        ttk.Combobox(
            options_frame, textvariable=self.click_type_var, state="readonly",
            width=10, values=["Single", "Double"],
        ).grid(row=0, column=3, padx=6, pady=4)

        # --- Click position ---
        pos_frame = ttk.LabelFrame(main, text="Click Position")
        pos_frame.grid(row=2, column=0, sticky="ew", **pad)

        self.pos_mode = tk.StringVar(value="cursor")
        ttk.Radiobutton(
            pos_frame, text="At cursor location", value="cursor",
            variable=self.pos_mode,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=2)
        ttk.Radiobutton(
            pos_frame, text="Fixed coordinate", value="fixed",
            variable=self.pos_mode,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=2)

        self.x_var = tk.StringVar(value="0")
        self.y_var = tk.StringVar(value="0")
        ttk.Label(pos_frame, text="X").grid(row=1, column=2, padx=(12, 2))
        ttk.Entry(pos_frame, textvariable=self.x_var, width=7).grid(
            row=1, column=3, padx=2)
        ttk.Label(pos_frame, text="Y").grid(row=1, column=4, padx=(8, 2))
        ttk.Entry(pos_frame, textvariable=self.y_var, width=7).grid(
            row=1, column=5, padx=2)

        self.pick_btn = ttk.Button(
            pos_frame, text="Pick Location", command=self._pick_location)
        self.pick_btn.grid(row=1, column=6, padx=8)

        # --- Repeat count ---
        repeat_frame = ttk.LabelFrame(main, text="Repeat")
        repeat_frame.grid(row=3, column=0, sticky="ew", **pad)

        self.repeat_mode = tk.StringVar(value="infinite")
        ttk.Radiobutton(
            repeat_frame, text="Until stopped", value="infinite",
            variable=self.repeat_mode,
        ).grid(row=0, column=0, sticky="w", padx=6, pady=2)
        ttk.Radiobutton(
            repeat_frame, text="Specific count", value="count",
            variable=self.repeat_mode,
        ).grid(row=1, column=0, sticky="w", padx=6, pady=2)

        self.repeat_count = tk.StringVar(value="10")
        ttk.Spinbox(
            repeat_frame, from_=1, to=1_000_000, width=8,
            textvariable=self.repeat_count, justify="center",
        ).grid(row=1, column=1, padx=6)
        ttk.Label(repeat_frame, text="clicks").grid(row=1, column=2, sticky="w")

        # --- Start / Stop ---
        control_frame = ttk.Frame(main)
        control_frame.grid(row=4, column=0, sticky="ew", pady=(8, 2))
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)

        self.start_btn = ttk.Button(
            control_frame, text=f"Start ({HOTKEY_LABEL})",
            command=self.start_clicking)
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=4)

        self.stop_btn = ttk.Button(
            control_frame, text=f"Stop ({HOTKEY_LABEL})",
            command=self.stop_clicking, state="disabled")
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=4)

        self.status_var = tk.StringVar(value="Stopped")
        self.status_label = ttk.Label(
            main, textvariable=self.status_var, anchor="center")
        self.status_label.grid(row=5, column=0, sticky="ew", pady=(6, 0))

    # --------------------------------------------------------------- helpers --
    def _interval_seconds(self):
        """Compute the total interval (seconds) from the spinbox values."""
        try:
            h = int(self.hours.get() or 0)
            m = int(self.minutes.get() or 0)
            s = int(self.seconds.get() or 0)
            ms = int(self.millis.get() or 0)
        except ValueError:
            raise ValueError("Interval fields accept whole numbers only.")

        total = h * 3600 + m * 60 + s + ms / 1000.0
        return max(total, MIN_INTERVAL)

    def _resolve_position(self):
        if self.pos_mode.get() != "fixed":
            return None
        try:
            return (int(self.x_var.get()), int(self.y_var.get()))
        except ValueError:
            raise ValueError("X and Y must be whole numbers for a fixed coordinate.")

    def _resolve_repeat_limit(self):
        if self.repeat_mode.get() != "count":
            return None
        try:
            limit = int(self.repeat_count.get())
        except ValueError:
            raise ValueError("Repeat count must be a whole number.")
        if limit < 1:
            raise ValueError("Repeat count must be at least 1.")
        return limit

    def _pick_location(self):
        """Capture the live cursor position after a short countdown."""
        self.pick_btn.config(state="disabled")
        self._countdown(3)

    def _countdown(self, n):
        if n > 0:
            self.pick_btn.config(text=f"{n}…")
            self.root.after(1000, lambda: self._countdown(n - 1))
        else:
            x, y = MouseController().position
            self.x_var.set(int(x))
            self.y_var.set(int(y))
            self.pos_mode.set("fixed")
            self.pick_btn.config(text="Pick Location", state="normal")

    # --------------------------------------------------------------- control --
    def toggle(self):
        """For the hotkey: stop if running, otherwise start."""
        if self.worker is not None:
            self.stop_clicking()
        else:
            self.start_clicking()

    def start_clicking(self):
        if self.worker is not None:
            return
        try:
            interval = self._interval_seconds()
            position = self._resolve_position()
            repeat_limit = self._resolve_repeat_limit()
        except ValueError as exc:
            messagebox.showwarning("Invalid value", str(exc))
            return

        button = ClickWorker.BUTTONS[self.button_var.get()]
        click_count = 2 if self.click_type_var.get() == "Double" else 1

        self.worker = ClickWorker(
            interval=interval,
            button=button,
            click_count=click_count,
            position=position,
            repeat_limit=repeat_limit,
            # Updating the GUI directly from the worker thread is unsafe;
            # bounce back to the main thread when finished.
            on_finish=lambda: self.root.after(0, self._on_worker_finished),
        )
        self.worker.start()

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("Running…")

    def stop_clicking(self):
        if self.worker is not None:
            self.worker.stop()
        # The UI is reset in _on_worker_finished once the worker ends.

    def _on_worker_finished(self):
        self.worker = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("Stopped")

    # ---------------------------------------------------------------- hotkey --
    def _start_hotkey_listener(self):
        def on_press(key):
            if key == HOTKEY:
                # The listener runs on its own thread; bounce to the GUI safely.
                self.root.after(0, self.toggle)

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()

    def _on_close(self):
        if self.worker is not None:
            self.worker.stop()
        if self._listener is not None:
            self._listener.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
