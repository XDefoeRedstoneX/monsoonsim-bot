import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import asyncio
from pyppeteer import connect
import game_api


# --- Main Application Class ---
class App(tk.Tk):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.title("MonsoonSim AI Controller")
        self.geometry("700x800")
        self.resizable(False, False)

        # --- Internal State ---
        self.browser = None
        self.page = None
        self.retail_task = None
        self.service_task = None
        self.full_task = None

        # Internal list to hold dynamic calc labels
        self.calc_labels = []
        self.calc_vars = []

        # --- NEW: Dictionary to store presets ---
        # Format: {"LocationName": ["P1_Name", "P3_Name"], ...}
        self.priority_presets = {}

        # --- Top Level Frames ---
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=5)

        notebook_frame = ttk.Frame(self)
        notebook_frame.pack(fill="both", expand=True, padx=10, pady=5)

        log_frame = ttk.LabelFrame(self, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Connection and Global Settings ---
        connection_frame = ttk.LabelFrame(top_frame, text="Connection", padding=10)
        connection_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.connect_button = ttk.Button(connection_frame, text="Connect to Browser", command=self.schedule_connect)
        self.connect_button.pack(side="left", padx=5)
        self.status_label = ttk.Label(connection_frame, text="Status: Disconnected", foreground="red")
        self.status_label.pack(side="left", padx=5)

        global_settings_frame = ttk.LabelFrame(top_frame, text="Global Settings", padding=10)
        global_settings_frame.pack(side="left", fill="x", padx=(5, 0))

        # Product Set Dropdown
        ttk.Label(global_settings_frame, text="Product Set:").pack(side="left", padx=5)
        self.product_set_var = tk.StringVar(value="Juice")
        product_set_dropdown = ttk.Combobox(global_settings_frame, textvariable=self.product_set_var,
                                            values=["Juice", "Mask", "Car", "Coffee", "Electronics"], state='readonly',
                                            width=10)
        product_set_dropdown.pack(side="left", padx=5)
        product_set_dropdown.bind("<<ComboboxSelected>>", self.handle_product_set_change)

        # Location Set Dropdown
        ttk.Label(global_settings_frame, text="Location Set:").pack(side="left", padx=5)
        self.location_set_var = tk.StringVar(value="Indonesia")
        location_set_dropdown = ttk.Combobox(global_settings_frame, textvariable=self.location_set_var,
                                             values=["Indonesia", "China"], state='readonly', width=10)
        location_set_dropdown.pack(side="left", padx=5)
        location_set_dropdown.bind("<<ComboboxSelected>>", self.handle_location_set_change)

        # --- Notebook (Tabbed Interface) ---
        notebook = ttk.Notebook(notebook_frame)
        notebook.pack(fill="both", expand=True, pady=5)

        retail_tab = ttk.Frame(notebook, padding=10)
        service_tab = ttk.Frame(notebook, padding=10)
        automation_tab = ttk.Frame(notebook, padding=10)

        notebook.add(retail_tab, text="Retail AI")
        notebook.add(service_tab, text="Service / HR")
        notebook.add(automation_tab, text="Full Automation")

        # --- RETAIL AI TAB ---
        self.setup_retail_tab(retail_tab)

        # --- SERVICE / HR TAB ---
        self.setup_service_tab(service_tab)

        # --- FULL AUTOMATION TAB ---
        self.setup_automation_tab(automation_tab)

        # --- Log Frame ---
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_area.pack(fill="both", expand=True)
        self.log_area.config(state="disabled")

        # --- Initialize dynamic labels ---
        self.update_dynamic_labels()

    def setup_retail_tab(self, tab):
        tab.columnconfigure(1, weight=1)
        # Manual controls
        manual_frame = ttk.LabelFrame(tab, text="Manual Control", padding=10)
        manual_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        manual_frame.columnconfigure(1, weight=1)

        ttk.Label(manual_frame, text="Target Location:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.location_var = tk.StringVar()
        self.location_dropdown = ttk.Combobox(manual_frame, textvariable=self.location_var, state='readonly')
        self.location_dropdown.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        # --- MODIFICATION: Bind location change to load preset ---
        self.location_dropdown.bind("<<ComboboxSelected>>", self.load_selected_preset)

        fetch_button = ttk.Button(manual_frame, text="Fetch Locations", command=self.schedule_fetch_locations)
        fetch_button.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(manual_frame, text="Target Fill Level:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.fill_percentage_var = tk.IntVar(value=100)
        fill_percentage_dropdown = ttk.Combobox(manual_frame, textvariable=self.fill_percentage_var,
                                                values=[100, 120, 140, 150, 160], state='readonly', width=5)
        fill_percentage_dropdown.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(manual_frame, text="%").grid(row=1, column=1, sticky="e")

        priority_frame = ttk.LabelFrame(manual_frame, text="Prioritize Products", padding=10)
        priority_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=10)
        self.priority_vars = {}
        self.priority_checkboxes = []
        for i, product_name in enumerate(game_api.ALL_PRODUCTS):
            var = tk.BooleanVar()
            # --- MODIFICATION: Add command to save preset ---
            chk = ttk.Checkbutton(priority_frame, text=product_name, variable=var, command=self.save_current_preset)
            chk.pack(side="left", expand=True, padx=10)
            self.priority_vars[product_name] = var
            self.priority_checkboxes.append(chk)

        replenish_button = ttk.Button(manual_frame, text="Run One-Time Replenish", command=self.handle_replenish_stock)
        replenish_button.grid(row=3, column=0, columnspan=3, pady=10)

        # Replenish Calculator
        calc_frame = ttk.LabelFrame(tab, text="Replenish Calculator (Dry Run)", padding=10)
        calc_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=10)
        calc_frame.columnconfigure(1, weight=1)

        calc_button = ttk.Button(calc_frame, text="Calculate Order", command=self.handle_calculate_replenish)
        calc_button.grid(row=0, column=0, rowspan=3, padx=10)

        for i in range(3):
            var = tk.StringVar(value=f"P{i + 1}: ---")
            label = ttk.Label(calc_frame, textvariable=var, font=("Segoe UI", 9, "bold"))
            label.grid(row=i, column=1, sticky="w", padx=10)
            self.calc_labels.append(label)
            self.calc_vars.append(var)

        # Automation controls for this tab
        auto_frame = ttk.LabelFrame(tab, text="Retail Automation Loop", padding=10)
        auto_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=10)
        self.retail_auto_button = ttk.Button(auto_frame, text="Start Retail Loop",
                                             command=lambda: self.toggle_automation('retail'), style="Accent.TButton")
        self.retail_auto_button.pack(side="left", padx=5)
        self.retail_auto_status = ttk.Label(auto_frame, text="Status: IDLE", foreground="blue")
        self.retail_auto_status.pack(side="left", padx=5)

    def setup_service_tab(self, tab):
        manual_frame = ttk.LabelFrame(tab, text="Manual Control", padding=10)
        manual_frame.pack(fill="x", pady=10)
        ttk.Label(manual_frame, text="Automate service requests based on your HR.ahk logic.").pack(pady=10)
        service_button = ttk.Button(manual_frame, text="Auto-Handle First Service Request",
                                    command=self.handle_service_request_button)
        service_button.pack(pady=10)

        auto_frame = ttk.LabelFrame(tab, text="Service Automation Loop", padding=10)
        auto_frame.pack(fill="x", pady=10)
        self.service_auto_button = ttk.Button(auto_frame, text="Start Service Loop",
                                              command=lambda: self.toggle_automation('service'), style="Accent.TButton")
        self.service_auto_button.pack(side="left", padx=5)
        self.service_auto_status = ttk.Label(auto_frame, text="Status: IDLE", foreground="blue")
        self.service_auto_status.pack(side="left", padx=5)

    def setup_automation_tab(self, tab):
        auto_frame = ttk.LabelFrame(tab, text="Master Automation Control", padding=10)
        auto_frame.pack(pady=20)
        self.full_auto_button = ttk.Button(auto_frame, text="Start Full Automation",
                                           command=lambda: self.toggle_automation('full'), style="Accent.TButton")
        self.full_auto_button.pack(side="left", padx=5)
        self.full_auto_status = ttk.Label(auto_frame, text="Status: IDLE", foreground="blue")
        self.full_auto_status.pack(side="left", padx=5)
        ttk.Label(tab,
                  text="This will run a daily loop performing all automated tasks:\n1. Handle Service Requests\n2. Replenish All Retail Stores",
                  justify="left").pack(pady=10)

    def toggle_automation(self, mode):
        if mode == 'retail':
            task_attr, button, label = 'retail_task', self.retail_auto_button, self.retail_auto_status
            start_text, stop_text = "Start Retail Loop", "Stop Retail Loop"
        elif mode == 'service':
            task_attr, button, label = 'service_task', self.service_auto_button, self.service_auto_status
            start_text, stop_text = "Start Service Loop", "Stop Service Loop"
        elif mode == 'full':
            task_attr, button, label = 'full_task', self.full_auto_button, self.full_auto_status
            start_text, stop_text = "Start Full Automation", "Stop Full Automation"
        else:
            return

        task = getattr(self, task_attr)

        if task and not task.done():
            task.cancel()
            button.config(text=start_text)
            label.config(text="Status: STOPPING...", foreground="orange")
        else:
            if not self.page:
                self.log_message("ERROR: Cannot start automation, not connected.", "red")
                return

            button.config(text=stop_text)
            label.config(text="Status: RUNNING", foreground="green")
            new_task = self.loop.create_task(self.run_automation_loop(mode))
            setattr(self, task_attr, new_task)

    async def run_automation_loop(self, mode):
        if mode == 'retail':
            button, label = self.retail_auto_button, self.retail_auto_status
            start_text = "Start Retail Loop"
        elif mode == 'service':
            button, label = self.service_auto_button, self.service_auto_status
            start_text = "Start Service Loop"
        elif mode == 'full':
            button, label = self.full_auto_button, self.full_auto_status
            start_text = "Start Full Automation"
        else:
            return

        try:
            while True:
                current_day_info = await game_api.get_current_day(self.page)
                current_day = current_day_info['current']
                self.log_message(f"--- Starting Day {current_day} ---", "purple")

                if mode in ['service', 'full']:
                    service_result = await game_api.handle_service_requests(self.page)
                    self.log_message(f"Service Check: {service_result}", "blue")

                if mode in ['retail', 'full']:
                    locations = self.location_dropdown['values']
                    if not locations:
                        self.log_message(f"AUTO-STOP ({mode}): No locations fetched.", "red")
                        break

                    target_percentage = self.fill_percentage_var.get()

                    # --- MODIFICATION: Load preset for each location in loop ---
                    for location in locations:
                        # Load the preset for this location
                        prioritized_products = self.priority_presets.get(location, [])
                        self.log_message(f"Using preset for {location}: {prioritized_products or 'None'}", "blue")

                        replenish_result = await game_api.procure_for_retail_location(self.page, location,
                                                                                      prioritized_products,
                                                                                      target_percentage)
                        self.log_message(f"Replenish ({location}): {replenish_result}")

                day_info = await game_api.wait_for_next_day(self.page, current_day)
                if day_info['current'] >= day_info['total']:
                    self.log_message("GAME OVER", "green")
                    break

        except asyncio.CancelledError:
            self.log_message(f"Automation loop ({mode}) stopped by user.", "orange")
        except Exception as e:
            self.log_message(f"AUTOMATION ERROR ({mode}): {e}", "red")
        finally:
            self.log_message(f"Automation loop ({mode}) terminated.", "blue")
            button.config(text=start_text)
            label.config(text="Status: IDLE", foreground="blue")

            if mode == 'retail':
                self.retail_task = None
            elif mode == 'service':
                self.service_task = None
            elif mode == 'full':
                self.full_task = None

    def update_dynamic_labels(self):
        """Updates all product-sensitive labels in the GUI."""
        try:
            new_products = game_api.ALL_PRODUCTS
            for i, new_name in enumerate(new_products):
                if i < len(self.priority_checkboxes):
                    self.priority_checkboxes[i].config(text=new_name)

            for i, new_name in enumerate(new_products):
                if i < len(self.calc_vars):
                    self.calc_vars[i].set(f"{new_name}: ---")

        except Exception as e:
            self.log_message(f"Error updating labels: {e}", "red")

    # --- NEW: Save the current checkbox state for the selected location ---
    def save_current_preset(self):
        location = self.location_var.get()
        if not location:
            return  # Don't save if no location is selected

        # Get all checked product names
        current_priorities = [name for name, var in self.priority_vars.items() if var.get()]

        # Save to the dictionary
        self.priority_presets[location] = current_priorities
        self.log_message(f"Preset saved for {location}: {current_priorities or 'None'}", "blue")

    # --- NEW: Load the preset when a location is selected ---
    def load_selected_preset(self, event=None):
        location = self.location_var.get()
        if not location:
            return  # Should not happen from a dropdown event, but good to check

        # Get the saved list, or an empty list if nothing is saved
        saved_priorities = self.priority_presets.get(location, [])
        self.log_message(f"Loaded preset for {location}: {saved_priorities or 'None'}", "blue")

        # Set the checkboxes
        for name, var in self.priority_vars.items():
            if name in saved_priorities:
                var.set(True)
            else:
                var.set(False)

    def handle_location_set_change(self, event=None):
        selected_set = self.location_set_var.get()
        try:
            game_api.set_active_location_set(selected_set)
            self.log_message(f"Location map switched to {selected_set}.", "blue")
            self.location_dropdown['values'] = []
            self.location_var.set("")
            # --- NEW: Clear presets when changing maps ---
            self.priority_presets = {}
            self.log_message("Priority presets cleared for new map.", "orange")
        except Exception as e:
            self.log_message(f"Error changing location set: {e}", "red")

    def handle_product_set_change(self, event=None):
        selected_set = self.product_set_var.get()
        try:
            old_products = list(self.priority_vars.keys())
            new_products = game_api.set_active_product_set(selected_set)
            new_priority_vars = {}

            # --- This logic is now critical to remap the presets ---
            # Create a name-to-name map (e.g., "Apple Juice" -> "Laptop")
            name_map = dict(zip(old_products, new_products))

            # Re-key the existing presets
            new_presets = {}
            for location, names in self.priority_presets.items():
                new_names_for_loc = [name_map.get(old_name) for old_name in names if name_map.get(old_name)]
                new_presets[location] = new_names_for_loc
            self.priority_presets = new_presets

            # Re-key the priority_vars
            for old_name, var_obj in self.priority_vars.items():
                new_name = name_map.get(old_name)
                if new_name:
                    new_priority_vars[new_name] = var_obj
            self.priority_vars = new_priority_vars

            self.update_dynamic_labels()
            self.load_selected_preset()  # Reload presets for current location
            self.log_message(f"GUI updated to {selected_set} set.", "blue")
            self.log_message(f"Presets re-mapped for {selected_set}.", "blue")

        except Exception as e:
            self.log_message(f"Error changing product set: {e}", "red")

    def handle_replenish_stock(self):
        location = self.location_var.get()
        if not location:
            self.log_message("ERROR: Select a location.", "red")
            return
        prioritized = [name for name, var in self.priority_vars.items() if var.get()]
        target_perc = self.fill_percentage_var.get()
        task = game_api.procure_for_retail_location(self.page, location, prioritized,
                                                    target_fill_percentage=target_perc)
        self.schedule_task(task)

    def handle_calculate_replenish(self):
        location = self.location_var.get()
        if not location:
            self.log_message("ERROR: Select a location for calculation.", "red")
            return
        prioritized = [name for name, var in self.priority_vars.items() if var.get()]
        target_perc = self.fill_percentage_var.get()
        task = self.run_calculation_task(location, prioritized, target_perc)
        self.schedule_task(task)

    async def run_calculation_task(self, location, prioritized, target_perc):
        try:
            self.log_message(f"[CALC] Running calculation for {location}...", "blue")
            for i, prod in enumerate(game_api.ALL_PRODUCTS):
                self.calc_vars[i].set(f"{prod}: ...")

            orders = await game_api.calculate_replenish_order(self.page, location, prioritized, target_perc)

            self.log_message(f"[CALC] Result for {location}: {orders}", "green")

            for i, prod_name in enumerate(game_api.ALL_PRODUCTS):
                if i < len(self.calc_vars):
                    qty = orders.get(prod_name, 0)
                    self.calc_vars[i].set(f"{prod_name}: {qty:,}")

            return f"[CALC] Calculation complete for {location}."

        except Exception as e:
            self.log_message(f"[CALC] ERROR: {e}", "red")
            for i, prod_name in enumerate(game_api.ALL_PRODUCTS):
                if i < len(self.calc_vars):
                    self.calc_vars[i].set(f"{prod_name}: ERROR")

    def handle_service_request_button(self):
        self.schedule_task(game_api.handle_service_requests(self.page))

    def schedule_fetch_locations(self):
        self.schedule_task(self.fetch_and_update_locations())

    async def fetch_and_update_locations(self):
        self.log_message("Scraping owned locations from KPI panel...")
        try:
            locations = await game_api.get_owned_retail_locations(self.page)
            self.location_dropdown['values'] = locations
            if locations:
                # --- MODIFICATION: Set location and auto-load its preset ---
                self.location_var.set(locations[0])
                self.log_message(f"SUCCESS: Found owned locations: {locations}", "green")
                self.load_selected_preset()  # Load preset for the first location
            else:
                self.log_message("WARNING: No owned locations found.", "orange")
        except Exception as e:
            self.log_message(f"ERROR fetching locations: {e}", "red")

    def schedule_task(self, task):
        self.loop.create_task(self.run_task_with_logging(task))

    async def run_task_with_logging(self, task):
        if not self.page:
            self.log_message("ERROR: Not connected.", "red")
            return
        try:
            result = await task
            if result: self.log_message(f"SUCCESS: {result}", "green")
        except Exception as e:
            self.log_message(f"ERROR: {e}", "red")

    def schedule_connect(self):
        self.connect_button.config(state="disabled")
        self.log_message("Attempting to connect...")
        self.loop.create_task(self.connect_to_browser())

    async def connect_to_browser(self):
        try:
            self.browser = await connect(browserURL="http://127.0.0.1:9222", defaultViewport=None)
            pages = await self.browser.pages()
            target_page = None
            for p in pages:
                if "monsoonsim.com" in p.url:
                    target_page = p
                    break
            if target_page:
                self.page = target_page
                self.status_label.config(text="Status: Connected", foreground="green")
                self.log_message(f"Connected to: {self.page.url}", "green")
                self.schedule_fetch_locations()
            else:
                raise Exception("MonsoonSIM page not found.")
        except Exception as e:
            self.status_label.config(text="Status: Failed", foreground="red")
            self.log_message(f"ERROR: Connection failed. {e}", "red")
        self.connect_button.config(state="normal")

    def log_message(self, msg, color="black"):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, f"{msg}\n")
        self.log_area.tag_config("red", foreground="red")
        self.log_area.tag_config("green", foreground="green")
        self.log_area.tag_config("blue", foreground="blue")
        self.log_area.tag_config("orange", foreground="#E69138")
        self.log_area.tag_config("purple", foreground="#800080")
        self.log_area.tag_add(color, "end-1c linestart", "end-1c lineend")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")


async def main_loop(app):
    while True:
        try:
            app.update()
            await asyncio.sleep(0.05)
        except tk.TclError:
            break


if __name__ == "__main__":
    main_event_loop = asyncio.get_event_loop()
    app = App(main_event_loop)


    def on_closing():
        print("Window closed, cancelling tasks...")
        if app.retail_task: app.retail_task.cancel()
        if app.service_task: app.service_task.cancel()
        if app.full_task: app.full_task.cancel()
        app.destroy()


    app.protocol("WM_DELETE_WINDOW", on_closing)
    main_event_loop.run_until_complete(main_loop(app))
