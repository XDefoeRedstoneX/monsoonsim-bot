"""Tkinter GUI for the MonsoonSim automation bot.

This is the single application entry point (run with ``python -m monsoon_bot``).
It wires the GUI to the Playwright-based :class:`~monsoon_bot.driver.MonsoonDriver`.
"""
from __future__ import annotations

import asyncio
import sys
import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, ttk

from . import config
from .async_tk import create_event_loop, pump_tk
from .driver import ActionResult, MonsoonDriver, connect_to_game
from .presets import PresetStore


class App(tk.Tk):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop

        # --- Config ---
        self.settings = config.load_settings()
        self.product_sets = config.load_product_sets()
        self.location_sets = config.load_location_sets()
        self.presets = PresetStore()

        default_ps = self.settings.get("default_product_set", next(iter(self.product_sets)))
        default_ls = self.settings.get("default_location_set", next(iter(self.location_sets)))
        self.active_product_set = self.product_sets[default_ps]
        self.active_location_map = self.location_sets[default_ls]

        # --- Runtime state ---
        self.connection = None
        self.driver: MonsoonDriver | None = None
        # One automation task slot per mode ("retail" / "service" / "full").
        self.tasks: dict[str, asyncio.Task | None] = {
            "retail": None, "service": None, "full": None}

        self.priority_vars: dict[str, tk.BooleanVar] = {}
        self.priority_checkboxes: list[ttk.Checkbutton] = []
        self.calc_vars: list[tk.StringVar] = []
        self.calc_labels: list[ttk.Label] = []

        # --- Window ---
        self.title("MonsoonSim AI Controller")
        self.minsize(560, 560)
        # Clamp the initial size to the screen so the window never opens larger
        # than the display (matters on small laptops and scaled HiDPI desktops).
        want_w, want_h = 760, 840
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{min(want_w, screen_w - 40)}x{min(want_h, screen_h - 80)}")

        self._build_ui()
        self._refresh_priority_widgets()

        # Single source of truth for each automation mode's widgets + labels.
        self.mode_ui = {
            "retail": {"button": self.retail_auto_button, "status": self.retail_auto_status,
                       "start": "Start Retail Loop", "stop": "Stop Retail Loop"},
            "service": {"button": self.service_auto_button, "status": self.service_auto_status,
                        "start": "Start Service Loop", "stop": "Stop Service Loop"},
            "full": {"button": self.full_auto_button, "status": self.full_auto_status,
                     "start": "Start Full Automation", "stop": "Stop Full Automation"},
        }

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=5)

        connection_frame = ttk.LabelFrame(top_frame, text="Connection", padding=10)
        connection_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.connect_button = ttk.Button(connection_frame, text="Connect to Browser",
                                          command=self.schedule_connect)
        self.connect_button.pack(side="left", padx=5)
        self.selftest_button = ttk.Button(connection_frame, text="Run Self-Test",
                                          command=self.schedule_self_test, state="disabled")
        self.selftest_button.pack(side="left", padx=5)
        self.status_label = ttk.Label(connection_frame, text="Status: Disconnected", foreground="red")
        self.status_label.pack(side="left", padx=5)

        global_frame = ttk.LabelFrame(top_frame, text="Global Settings", padding=10)
        global_frame.pack(side="left", fill="x", padx=(5, 0))

        ttk.Label(global_frame, text="Product Set:").pack(side="left", padx=5)
        self.product_set_var = tk.StringVar(value=self.active_product_set.name)
        ps_combo = ttk.Combobox(global_frame, textvariable=self.product_set_var,
                                values=list(self.product_sets.keys()), state="readonly", width=11)
        ps_combo.pack(side="left", padx=5)
        ps_combo.bind("<<ComboboxSelected>>", self.handle_product_set_change)

        ttk.Label(global_frame, text="Location Set:").pack(side="left", padx=5)
        self.location_set_var = tk.StringVar(value=next(
            (n for n, m in self.location_sets.items() if m is self.active_location_map),
            next(iter(self.location_sets))))
        ls_combo = ttk.Combobox(global_frame, textvariable=self.location_set_var,
                                values=list(self.location_sets.keys()), state="readonly", width=11)
        ls_combo.pack(side="left", padx=5)
        ls_combo.bind("<<ComboboxSelected>>", self.handle_location_set_change)

        # --- Notebook ---
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)
        retail_tab = ttk.Frame(notebook, padding=10)
        service_tab = ttk.Frame(notebook, padding=10)
        automation_tab = ttk.Frame(notebook, padding=10)
        notebook.add(retail_tab, text="Retail AI")
        notebook.add(service_tab, text="Service / HR")
        notebook.add(automation_tab, text="Full Automation")
        self._setup_retail_tab(retail_tab)
        self._setup_service_tab(service_tab)
        self._setup_automation_tab(automation_tab)

        # --- Log ---
        log_frame = ttk.LabelFrame(self, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_area.pack(fill="both", expand=True)
        # Configure colour tags once; log_message just applies them per line.
        for tag, fg in (("red", "red"), ("green", "green"), ("blue", "blue"),
                        ("orange", "#E69138"), ("purple", "#800080")):
            self.log_area.tag_config(tag, foreground=fg)
        self.log_area.config(state="disabled")

    def _setup_retail_tab(self, tab):
        tab.columnconfigure(1, weight=1)
        manual = ttk.LabelFrame(tab, text="Manual Control", padding=10)
        manual.grid(row=0, column=0, columnspan=3, sticky="ew")
        manual.columnconfigure(1, weight=1)

        ttk.Label(manual, text="Target Location:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.location_var = tk.StringVar()
        self.location_dropdown = ttk.Combobox(manual, textvariable=self.location_var, state="readonly")
        self.location_dropdown.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.location_dropdown.bind("<<ComboboxSelected>>", self.load_selected_preset)
        ttk.Button(manual, text="Fetch Locations", command=self.schedule_fetch_locations
                   ).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(manual, text="Target Fill Level:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.fill_percentage_var = tk.IntVar(value=self.settings.get("default_fill_level", 100))
        ttk.Combobox(manual, textvariable=self.fill_percentage_var,
                     values=self.settings.get("fill_level_options", [100]),
                     state="readonly", width=5).grid(row=1, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(manual, text="%").grid(row=1, column=1, sticky="e")

        self.priority_frame = ttk.LabelFrame(manual, text="Prioritize Products", padding=10)
        self.priority_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=10)

        ttk.Button(manual, text="Run One-Time Replenish", command=self.handle_replenish_stock
                   ).grid(row=3, column=0, columnspan=3, pady=10)

        calc = ttk.LabelFrame(tab, text="Replenish Calculator (Dry Run)", padding=10)
        calc.grid(row=1, column=0, columnspan=3, sticky="ew", pady=10)
        calc.columnconfigure(1, weight=1)
        ttk.Button(calc, text="Calculate Order", command=self.handle_calculate_replenish
                   ).grid(row=0, column=0, rowspan=3, padx=10)
        self.calc_frame = calc

        auto = ttk.LabelFrame(tab, text="Retail Automation Loop", padding=10)
        auto.grid(row=2, column=0, columnspan=3, sticky="ew", pady=10)
        self.retail_auto_button = ttk.Button(auto, text="Start Retail Loop",
                                              command=lambda: self.toggle_automation("retail"))
        self.retail_auto_button.pack(side="left", padx=5)
        self.retail_auto_status = ttk.Label(auto, text="Status: IDLE", foreground="blue")
        self.retail_auto_status.pack(side="left", padx=5)

    def _setup_service_tab(self, tab):
        manual = ttk.LabelFrame(tab, text="Manual Control", padding=10)
        manual.pack(fill="x", pady=10)
        ttk.Label(manual, text="Auto-assign mandays for the first incoming service request."
                  ).pack(pady=10)
        ttk.Button(manual, text="Auto-Handle First Service Request",
                   command=self.handle_service_request_button).pack(pady=10)

        auto = ttk.LabelFrame(tab, text="Service Automation Loop", padding=10)
        auto.pack(fill="x", pady=10)
        self.service_auto_button = ttk.Button(auto, text="Start Service Loop",
                                               command=lambda: self.toggle_automation("service"))
        self.service_auto_button.pack(side="left", padx=5)
        self.service_auto_status = ttk.Label(auto, text="Status: IDLE", foreground="blue")
        self.service_auto_status.pack(side="left", padx=5)

    def _setup_automation_tab(self, tab):
        auto = ttk.LabelFrame(tab, text="Master Automation Control", padding=10)
        auto.pack(pady=20)
        self.full_auto_button = ttk.Button(auto, text="Start Full Automation",
                                            command=lambda: self.toggle_automation("full"))
        self.full_auto_button.pack(side="left", padx=5)
        self.full_auto_status = ttk.Label(auto, text="Status: IDLE", foreground="blue")
        self.full_auto_status.pack(side="left", padx=5)
        ttk.Label(tab, justify="left", text=(
            "Runs a daily loop performing all automated tasks:\n"
            "1. Handle Service Requests\n"
            "2. Replenish All Retail Stores")).pack(pady=10)

    # ------------------------------------------------- dynamic priority widgets
    def _refresh_priority_widgets(self):
        """Rebuild the priority checkboxes and calc labels for the active set."""
        for chk in self.priority_checkboxes:
            chk.destroy()
        for label in self.calc_labels:
            label.destroy()

        self.priority_vars = {}
        self.priority_checkboxes = []
        for name in self.active_product_set.names:
            var = tk.BooleanVar()
            chk = ttk.Checkbutton(self.priority_frame, text=name, variable=var,
                                  command=self.save_current_preset)
            chk.pack(side="left", expand=True, padx=10)
            self.priority_vars[name] = var
            self.priority_checkboxes.append(chk)

        self.calc_vars = []
        self.calc_labels = []
        for i, name in enumerate(self.active_product_set.names):
            var = tk.StringVar(value=f"{name}: ---")
            label = ttk.Label(self.calc_frame, textvariable=var, font=("Segoe UI", 9, "bold"))
            label.grid(row=i, column=1, sticky="w", padx=10)
            self.calc_vars.append(var)
            self.calc_labels.append(label)

    # ------------------------------------------------------------- presets
    def _preset_key(self, location: str) -> str:
        # Namespaced by product set so different sets don't clobber each other.
        return f"{self.active_product_set.name}::{location}"

    def save_current_preset(self):
        location = self.location_var.get()
        if not location:
            return
        priorities = [name for name, var in self.priority_vars.items() if var.get()]
        self.presets.set(self._preset_key(location), priorities)
        self.log_message(f"Preset saved for {location}: {priorities or 'None'}", "blue")

    def load_selected_preset(self, event=None):
        location = self.location_var.get()
        if not location:
            return
        saved = self.presets.get(self._preset_key(location))
        for name, var in self.priority_vars.items():
            var.set(name in saved)
        self.log_message(f"Loaded preset for {location}: {saved or 'None'}", "blue")

    # ------------------------------------------------- global settings handlers
    def handle_product_set_change(self, event=None):
        name = self.product_set_var.get()
        self.active_product_set = self.product_sets[name]
        if self.driver:
            self.driver.product_set = self.active_product_set
        self._refresh_priority_widgets()
        self.load_selected_preset()
        self.log_message(f"Product set switched to {name}.", "blue")

    def handle_location_set_change(self, event=None):
        name = self.location_set_var.get()
        self.active_location_map = self.location_sets[name]
        if self.driver:
            self.driver.location_map = self.active_location_map
            self.driver.location_set_name = name
        self.location_dropdown["values"] = []
        self.location_var.set("")
        self.log_message(f"Location map switched to {name}.", "blue")

    # ------------------------------------------------------------- retail tasks
    def handle_replenish_stock(self):
        location = self.location_var.get()
        if not location:
            self.log_message("ERROR: Select a location.", "red")
            return
        prioritized = [name for name, var in self.priority_vars.items() if var.get()]
        self.schedule_task(self.driver.procure_for_retail_location(
            location, prioritized, target_fill_percentage=self.fill_percentage_var.get()))

    def handle_calculate_replenish(self):
        location = self.location_var.get()
        if not location:
            self.log_message("ERROR: Select a location for calculation.", "red")
            return
        prioritized = [name for name, var in self.priority_vars.items() if var.get()]
        self.schedule_task(self._run_calculation(location, prioritized,
                                                 self.fill_percentage_var.get()))

    async def _run_calculation(self, location, prioritized, target):
        self.log_message(f"[CALC] Running calculation for {location}...", "blue")
        for var in self.calc_vars:
            var.set(var.get().split(":")[0] + ": ...")
        try:
            orders = await self.driver.calculate_replenish_order(location, prioritized, target)
            self.log_message(f"[CALC] Result for {location}: {orders}", "green")
            for i, name in enumerate(self.active_product_set.names):
                self.calc_vars[i].set(f"{name}: {orders.get(name, 0):,}")
        except Exception as exc:
            self.log_message(f"[CALC] ERROR: {exc}", "red")
            for i, name in enumerate(self.active_product_set.names):
                self.calc_vars[i].set(f"{name}: ERROR")

    def handle_service_request_button(self):
        self.schedule_task(self.driver.handle_service_requests())

    # ------------------------------------------------------------- locations
    def schedule_fetch_locations(self):
        self.schedule_task(self._fetch_locations())

    async def _fetch_locations(self):
        self.log_message("Scraping owned locations from KPI panel...")
        locations = await self.driver.get_owned_retail_locations()
        self.location_dropdown["values"] = locations
        if locations:
            self.location_var.set(locations[0])
            self.log_message(f"SUCCESS: Found owned locations: {locations}", "green")
            self.load_selected_preset()
        else:
            self.log_message("WARNING: No owned locations found.", "orange")

    # ------------------------------------------------------------- automation
    def toggle_automation(self, mode):
        ui = self.mode_ui[mode]
        task = self.tasks[mode]

        if task and not task.done():
            task.cancel()
            ui["button"].config(text=ui["start"])
            ui["status"].config(text="Status: STOPPING...", foreground="orange")
        else:
            if not self.driver:
                self.log_message("ERROR: Cannot start automation, not connected.", "red")
                return
            ui["button"].config(text=ui["stop"])
            ui["status"].config(text="Status: RUNNING", foreground="green")
            self.tasks[mode] = self.loop.create_task(self.run_automation_loop(mode))

    async def run_automation_loop(self, mode):
        ui = self.mode_ui[mode]
        try:
            while True:
                day = await self.driver.get_current_day()
                # Detect the end BEFORE waiting, so the final day exits cleanly
                # instead of timing out in wait_for_next_day.
                if day["current"] >= day["total"]:
                    self.log_message("GAME OVER", "green")
                    break

                current = day["current"]
                self.log_message(f"--- Starting Day {current} ---", "purple")

                if mode in ("service", "full"):
                    result = await self.driver.handle_service_requests()
                    self.log_message(f"Service Check: {result.message}",
                                     "blue" if result.ok else "red")

                if mode in ("retail", "full"):
                    locations = self.location_dropdown["values"]
                    if not locations:
                        self.log_message(f"AUTO-STOP ({mode}): No locations fetched.", "red")
                        break
                    target = self.fill_percentage_var.get()
                    failures = 0
                    for location in locations:
                        prioritized = self.presets.get(self._preset_key(location))
                        result = await self.driver.procure_for_retail_location(
                            location, prioritized, target)
                        self.log_message(f"Replenish ({location}): {result.message}",
                                         "black" if result.ok else "red")
                        if not result.ok:
                            failures += 1
                    # Every location failing means a real misconfiguration
                    # (e.g. wrong location map); stop rather than spam each day.
                    if failures == len(locations):
                        self.log_message(
                            f"AUTO-STOP ({mode}): all {failures} locations failed.", "red")
                        break

                # Re-read the day: the in-game clock may have advanced while we
                # worked, in which case we should not wait again.
                if (await self.driver.get_current_day())["current"] == current:
                    await self.driver.wait_for_next_day(current)
        except asyncio.CancelledError:
            self.log_message(f"Automation loop ({mode}) stopped by user.", "orange")
        except Exception as exc:
            self.log_message(f"AUTOMATION ERROR ({mode}): {exc}", "red")
        finally:
            self.log_message(f"Automation loop ({mode}) terminated.", "blue")
            ui["button"].config(text=ui["start"])
            ui["status"].config(text="Status: IDLE", foreground="blue")
            self.tasks[mode] = None

    # ------------------------------------------------------------- connection
    def schedule_connect(self):
        self.connect_button.config(state="disabled")
        self.log_message("Attempting to connect...")
        self.loop.create_task(self._connect())

    async def _connect(self):
        try:
            self.connection = await connect_to_game(self.settings)
            self.driver = MonsoonDriver(self.connection.page, self.active_product_set,
                                        self.active_location_map, self.settings)
            self.driver.location_set_name = self.location_set_var.get()
            self.status_label.config(text="Status: Connected", foreground="green")
            self.selftest_button.config(state="normal")
            self.log_message(f"Connected to: {self.connection.page.url}", "green")
            await self._fetch_locations()
        except Exception as exc:
            self.status_label.config(text="Status: Failed", foreground="red")
            self.log_message(f"ERROR: Connection failed. {exc}", "red")
        finally:
            self.connect_button.config(state="normal")

    def schedule_self_test(self):
        self.schedule_task(self._run_self_test())

    async def _run_self_test(self):
        self.log_message("--- Running self-test ---", "purple")
        rows = await self.driver.self_test()
        for name, ok, detail in rows:
            self.log_message(f"[{'OK ' if ok else 'FAIL'}] {name}: {detail}",
                             "green" if ok else "red")

    # ------------------------------------------------------------- task runner
    def schedule_task(self, coro):
        self.loop.create_task(self._run_with_logging(coro))

    async def _run_with_logging(self, coro):
        if not self.driver:
            self.log_message("ERROR: Not connected.", "red")
            coro.close()
            return
        try:
            result = await coro
            if isinstance(result, ActionResult):
                self.log_message(result.message, "green" if result.ok else "red")
            elif result:
                self.log_message(f"SUCCESS: {result}", "green")
        except Exception as exc:
            self.log_message(f"ERROR: {exc}", "red")

    # ------------------------------------------------------------- logging
    def log_message(self, msg, color="black"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_area.tag_add(color, "end-1c linestart", "end-1c lineend")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")


def _enable_hidpi():
    """Best-effort per-monitor DPI awareness on Windows (no-op elsewhere)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def main():
    _enable_hidpi()
    loop = create_event_loop()
    app = App(loop)

    def on_closing():
        for task in app.tasks.values():
            if task:
                task.cancel()
        if app.connection:
            loop.create_task(app.connection.close())
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_closing)
    try:
        loop.run_until_complete(pump_tk(app))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
