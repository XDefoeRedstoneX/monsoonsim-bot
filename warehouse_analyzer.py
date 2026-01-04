import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import asyncio
from pyppeteer import connect
import game_api  # We still use the shared library

# --- Global variables ---
browser = None
page = None


# --- Main Application Class ---
class App(tk.Tk):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.title("MonsoonSim Warehouse Analyzer")
        self.geometry("800x600")

        # --- Connection Frame ---
        connection_frame = ttk.LabelFrame(self, text="Connection", padding=10)
        connection_frame.pack(fill="x", padx=10, pady=5, side=tk.TOP)
        self.connect_button = ttk.Button(connection_frame, text="Connect to Browser", command=self.schedule_connect)
        self.connect_button.pack(side="left", padx=5)
        self.status_label = ttk.Label(connection_frame, text="Status: Disconnected", foreground="red")
        self.status_label.pack(side="left", padx=5)

        # --- Controls Frame ---
        controls_frame = ttk.LabelFrame(self, text="Controls", padding=10)
        controls_frame.pack(fill="x", padx=10, pady=5)

        # --- THIS IS THE FIX: Added Product Set Selection ---
        product_set_frame = ttk.Frame(controls_frame)
        product_set_frame.pack(pady=5)
        ttk.Label(product_set_frame, text="Active Product Set:").pack(side="left", padx=5)
        self.product_set_var = tk.StringVar(value="Juice")
        product_set_dropdown = ttk.Combobox(product_set_frame, textvariable=self.product_set_var,
                                            values=["Juice", "Mask"], state='readonly')
        product_set_dropdown.pack(side="left", padx=5)
        product_set_dropdown.bind("<<ComboboxSelected>>", self.handle_product_set_change)

        refresh_button = ttk.Button(controls_frame, text="Refresh Warehouse Data", command=self.schedule_refresh,
                                    style="Accent.TButton")
        refresh_button.pack(pady=10)
        ttk.Style().configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        # --- Data Table Frame ---
        table_frame = ttk.LabelFrame(self, text="Warehouse Analysis", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Create the Treeview (table)
        columns = ("warehouse", "product", "stock", "space", "order")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")

        # Define headings
        self.tree.heading("warehouse", text="Warehouse Name")
        self.tree.heading("product", text="Product")
        self.tree.heading("stock", text="Current Stock")
        self.tree.heading("space", text="Space Used (m²)")
        self.tree.heading("order", text="Order to Fill 100%")

        # Configure column widths
        self.tree.column("warehouse", width=150)
        self.tree.column("product", width=120)
        self.tree.column("stock", width=100, anchor="e")  # 'e' for east (right-align)
        self.tree.column("space", width=120, anchor="center")
        self.tree.column("order", width=150, anchor="e")

        self.tree.pack(fill="both", expand=True)

    def handle_product_set_change(self, event=None):
        """Called when the user selects a new product set from the dropdown."""
        selected_set = self.product_set_var.get()
        try:
            game_api.set_active_product_set(selected_set)
            messagebox.showinfo("Success", f"Product set switched to {selected_set}. Please refresh data.")
        except ValueError as e:
            messagebox.showerror("Error", f"Error changing product set: {e}")

    def schedule_refresh(self):
        """Schedules the warehouse analysis task."""
        self.loop.create_task(self.run_analysis())

    async def run_analysis(self):
        """Clears the table, runs the API function, and populates the table."""
        if not page:
            messagebox.showerror("Error", "Not connected to the browser. Please connect first.")
            return

        # Clear existing data from the table
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            # Call the new function from our API
            analysis_data = await game_api.analyze_warehouses(page)

            # Populate the table with new data
            if analysis_data:
                # Get the number of unique warehouses
                num_warehouses = len(set(d['warehouse'] for d in analysis_data))
                for row_data in analysis_data:
                    self.tree.insert("", tk.END, values=(
                        row_data["warehouse"],
                        row_data["product"],
                        f'{row_data["current_stock"]:,}',  # Format with comma
                        row_data["space_used_m2"],
                        f'{row_data["fill_order_suggestion"]:,}'  # Format with comma
                    ))
                messagebox.showinfo("Success", f"Successfully analyzed {num_warehouses} warehouses.")
            else:
                messagebox.showwarning("No Data", "Could not find any warehouse data to analyze.")

        except Exception as e:
            messagebox.showerror("Analysis Failed", f"An error occurred:\n{e}")

    def schedule_connect(self):
        self.connect_button.config(state="disabled")
        self.loop.create_task(self.connect_to_browser())

    async def connect_to_browser(self):
        global browser, page
        try:
            browser = await connect(browserURL="http://127.0.0.1:9222", defaultViewport=None)
            pages = await browser.pages()
            target_page = None
            for p in pages:
                if "monsoonsim.com" in p.url:
                    target_page = p
                    break
            if target_page:
                page = target_page
                self.status_label.config(text="Status: Connected", foreground="green")
            else:
                self.status_label.config(text="Status: Failed", foreground="red")
        except Exception as e:
            self.status_label.config(text="Status: Failed", foreground="red")
        self.connect_button.config(state="normal")


# --- Custom Main Loop to integrate Tkinter and Asyncio ---
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
    main_event_loop.run_until_complete(main_loop(app))

