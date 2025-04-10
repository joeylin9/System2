import tkinter as tk
import threading
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from System2_Equipment import Pump, ReadFloatsPLC, OneBitClass, WriteFloatsPLC
from System2_utils import Graph

class PumpControl:
    """Encapsulates all UI elements for a pump."""
    def __init__(self, connect, on_button, off_button, channel_var, flow_var):
        self.connect = connect  # Connect button
        self.on_button = on_button  # On button
        self.off_button = off_button  # Off button
        self.channel_var = channel_var  # Channel number input variable
        self.flow_var = flow_var  #  input variable

    def set_serial_obj(self, serial_obj):
        print('Setting pump serial object')
        self.serial_obj = serial_obj

# holds all pump and plc addresses
addresses = {
    'Pumps': [9],
    'Temperatures': [28710, 28712, 28714],
    'Pressure Transmitters': [28750, 28752, 28754],
    'Pressure Regulators': [28770, 28772],
    'Pressure In/Outs': [8352, 8353, 8354, 8355, 8356, 8357],
    'Valves': [8358],
    'Stirrers': [28790, 28792, 28794],
    'Drums': [16387]
}

class System2:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("System Two Control Panel")
        self.root.state('zoomed')  # Maximize window for better visibility
        
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True)
        
        # Split the interface into equipment control and graph areas
        left_panel = tk.Frame(main_frame)
        left_panel.pack(side="left", fill="y", padx=10, pady=10)
        
        right_panel = tk.Frame(main_frame)
        right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        tk.Label(left_panel, text="System Two Control", font=("Arial", 18, "bold")).pack(pady=10)

        # Create a canvas with scrollbars for equipment control
        vscrollbar = tk.Scrollbar(left_panel, orient="vertical")
        vscrollbar.pack(fill="y", side="right", expand=False)
        
        hscrollbar = tk.Scrollbar(left_panel, orient="horizontal")
        hscrollbar.pack(fill="x", side="bottom", expand=False)
        
        canvas = tk.Canvas(
            left_panel,
            bd=0,
            highlightthickness=0,
            yscrollcommand=vscrollbar.set,
            xscrollcommand=hscrollbar.set,
            width=500,  # Fixed width for equipment panel
        )
        canvas.pack(side="left", fill="both", expand=True)
        vscrollbar.config(command=canvas.yview)
        hscrollbar.config(command=canvas.xview)

        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

        self.interior = tk.Frame(canvas)
        canvas.create_window(0, 0, window=self.interior, anchor="nw")

        def configure_interior(event):
            # Update the scrollbars to match the size of the inner frame.
            size = (self.interior.winfo_reqwidth(), self.interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if self.interior.winfo_reqwidth() != canvas.winfo_width():
                # Update the canvas's width to fit the inner frame.
                canvas.config(width=self.interior.winfo_reqwidth())
            if self.interior.winfo_reqheight() != canvas.winfo_height():
                # Update the canvas's width to fit the inner frame.
                canvas.config(height=self.interior.winfo_reqheight())

        self.interior.bind("<Configure>", configure_interior)

        gui_frame = tk.Frame(self.interior)

        ### ---EQUIPMENT--- ###
        self.equipment_frame = tk.Frame(gui_frame)
        enter_button = tk.Button(self.equipment_frame, text="Assign and Read Data", command=self.open_assign)
        enter_button.pack(anchor="nw", padx=15, pady=15)

        ### --- PUMPS --- ###
        self.pumps_list = ["Pump 1"]
        self.pump_connect_vars = [False] * len(self.pumps_list)
        self.pump_port_vars = [None] * len(self.pumps_list)
        self.pump_controls = {}  # Dictionary to store UI elements
        self.create_pump_ui()

        # Maps equipment type to a dictionary that maps a specific equipment to either the current_label
        # for temp and pressure transmitters, or the current value variable for pressure regulator and stirrer
        self.equipment_data = {}

        # Maps "buttons" or "vars" to a dicitonary that equipment name to variable, 
        # variable tracks if that equipment is connected (1) or not (0)
        self.connect_dictionary = {"buttons": {}, "vars": {}}

        # Maps equipment type to a dictionary that maps specific equipment number to a register value
        self.register_dictionary = {}

        self.create_temperatures_section()
        self.create_pressure_transmitter_section()
        self.create_pressure_regulator_section()
        self.create_pressure_inout_section()
        self.create_valves_section()
        self.create_stirrer_section()
        self.create_drum_section()

        self.equipment_frame.grid(row=0, column=0, sticky="nw")

        # Initiate Classes
        plc_host_num = "169.254.83.200"
        self.temperature_plc = ReadFloatsPLC(plc_host_num, 502)
        self.pressure_transmitter_plc = ReadFloatsPLC(plc_host_num, 502)

        self.pressure_inout_plc = OneBitClass(plc_host_num)
        self.valve_plc = OneBitClass(plc_host_num)
        self.drum_plc = OneBitClass(plc_host_num)

        self.stirrer_plc = WriteFloatsPLC(plc_host_num)
        self.pressure_regulator_plc = WriteFloatsPLC(plc_host_num)

        gui_frame.pack()

        # Setup for graphs
        self.setup_graphs(right_panel)

        tk.Button(self.root, text="TEST", command=self.test).place(x=10, y=10)
        self.root.bind("<KeyPress>", self.exit_shortcut) # press escape button on keyboard to close the GUI
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def setup_graphs(self, parent_frame):
        """Create the graph UI and initialize graph objects"""
        # Create frame for graph controls
        graph_control_frame = tk.Frame(parent_frame)
        graph_control_frame.pack(fill="x", pady=10)
        
        # Labels
        tk.Label(graph_control_frame, text="Data Visualization", font=("Arial", 16, "bold")).pack(anchor="w")
        
        # Create buttons for graph control
        control_buttons_frame = tk.Frame(graph_control_frame)
        control_buttons_frame.pack(fill="x", pady=5)
        
        # Time window control
        tk.Label(control_buttons_frame, text="Time Window:").grid(row=0, column=0, padx=5)
        self.time_window_var = tk.StringVar(value="120")
        time_window_entry = tk.Entry(control_buttons_frame, textvariable=self.time_window_var, width=6)
        time_window_entry.grid(row=0, column=1, padx=5)
        tk.Label(control_buttons_frame, text="seconds").grid(row=0, column=2, padx=5)
        tk.Button(control_buttons_frame, text="Set", command=self.set_time_window).grid(row=0, column=3, padx=5)
        
        # Export data button
        tk.Button(control_buttons_frame, text="Export Data", command=self.export_graph_data).grid(row=0, column=4, padx=20)
        
        # Clear data button
        tk.Button(control_buttons_frame, text="Clear All Data", command=self.clear_graph_data).grid(row=0, column=5, padx=5)
        
        # Start/Stop graphing
        self.graph_running = True
        self.graph_button = tk.Button(control_buttons_frame, text="Stop Graphing", bg="light coral", command=self.toggle_graphing)
        self.graph_button.grid(row=0, column=6, padx=20)
        
        # Create a frame for the graphs
        graph_frame = tk.Frame(parent_frame)
        graph_frame.pack(fill="both", expand=True, pady=5)
        
        # Configure matplotlib
        fig, self.plot_axes = plt.subplots(2, 2, figsize=(10, 8))
        self.plot_axes = self.plot_axes.flatten()
        
        # Convert to a tkinter widget
        canvas = FigureCanvasTkAgg(fig, master=graph_frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas = canvas
        
        # Initialize dictionaries for graph data
        self.init_graph_data()
        
        # Create data series selector frame
        data_selector_frame = tk.Frame(parent_frame)
        data_selector_frame.pack(fill="x", pady=5)
        
        # Create tabs for different types of data
        self.create_data_selector_tabs(data_selector_frame)
        
        # Start the graph
        self.start_graph()

    def init_graph_data(self):
        """Initialize dictionaries for the graph data"""
        # For each data type, create a dictionary to store the series
        # Format: {series_name: [global_switch(bool), active_status(bool), data_points(list)]}
        
        # Temperature data
        self.temperatures_dict = {}
        for name in self.temperatures_list:
            self.temperatures_dict[name] = [True, True, []]
        
        # Pressure data
        self.pressures_dict = {}
        for name in self.pressure_transmitters_list:
            self.pressures_dict[name] = [True, True, []]
        
        # Balance data - placeholder for any balance equipment
        self.balances_dict = {}
        
        #  data
        self.flow_rates_dict = {}
        for pump_name in self.pumps_list:
            self.flow_rates_dict[pump_name] = [True, True, []]
        
        # Create the graph object
        self.graph = Graph(
            self.temperatures_dict,
            self.pressures_dict, 
            self.balances_dict,
            self.flow_rates_dict,
            max_points=1000,  # Store up to 1000 data points per series
            update_interval=0.5  # Update every 0.5 seconds
        )

    def create_data_selector_tabs(self, parent_frame):
        """Create tabs for selecting which data series to display"""
        # Create notebook for tabs
        notebook = tk.Frame(parent_frame)
        notebook.pack(fill="x")
        
        # Create tab buttons
        tab_frame = tk.Frame(notebook)
        tab_frame.pack(fill="x")
        
        self.tab_buttons = []
        self.tab_frames = []
        
        tab_names = ["Temperature", "Pressure", "Flow_Rate"]
        
        for i, name in enumerate(tab_names):
            button = tk.Button(tab_frame, text=name, 
                              command=lambda idx=i: self.switch_tab(idx))
            button.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            self.tab_buttons.append(button)
        
        # Create content frames for each tab
        self.tab_content_frame = tk.Frame(notebook)
        self.tab_content_frame.pack(fill="x", expand=True)
        
        # Create content for temperature tab
        temp_frame = tk.Frame(self.tab_content_frame)
        self.create_series_selectors(temp_frame, "Temperatures", self.temperatures_list)
        self.tab_frames.append(temp_frame)
        
        # Create content for pressure tab
        pressure_frame = tk.Frame(self.tab_content_frame)
        self.create_series_selectors(pressure_frame, "Pressures", self.pressure_transmitters_list)
        self.tab_frames.append(pressure_frame)
        
        # Create content for flow rate tab
        flow_frame = tk.Frame(self.tab_content_frame)
        self.create_series_selectors(flow_frame, "Flow_Rates", self.pumps_list)
        self.tab_frames.append(flow_frame)
        
        # Show first tab by default
        self.switch_tab(0)

    def switch_tab(self, tab_index):
        """Switch between data selector tabs"""
        for i, button in enumerate(self.tab_buttons):
            if i == tab_index:
                button.config(relief="sunken", bg="light blue")
            else:
                button.config(relief="raised", bg="SystemButtonFace")
        
        for i, frame in enumerate(self.tab_frames):
            if i == tab_index:
                frame.pack(fill="x", expand=True)
            else:
                frame.pack_forget()

    def create_series_selectors(self, parent_frame, data_type, series_list):
        """
        Create checkboxes for each data series that directly control visibility.
        
        Args:
            parent_frame: Frame to place checkboxes in
            data_type: Type of data (Temperature, Pressure, etc.)
            series_list: List of series names
        """
        # Dict to store checkbox variables
        if not hasattr(self, 'checkbox_vars'):
            self.checkbox_vars = {}
        
        # Add a 'select all' button
        all_button = tk.Button(parent_frame, text=f"Select All {data_type}", 
                            command=lambda: self.toggle_all_series(data_type.lower(), True))
        all_button.pack(side="left", padx=5, pady=5)
        
        # Add a 'deselect all' button
        none_button = tk.Button(parent_frame, text=f"Deselect All {data_type}", 
                            command=lambda: self.toggle_all_series(data_type.lower(), False))
        none_button.pack(side="left", padx=5, pady=5)
        
        # Create a frame for the checkboxes
        checkbox_frame = tk.Frame(parent_frame)
        checkbox_frame.pack(fill="x", padx=5, pady=5)
        
        # Create a checkbox for each series
        for i, name in enumerate(series_list):
            # Get the dictionary for this data type
            data_dict = getattr(self.graph, f"{data_type.lower()}_dict")
            
            # Initialize checkbox variable based on current series visibility
            is_visible = data_dict[name][1] if name in data_dict else True
            
            # Create variable and store it
            var = tk.BooleanVar(value=is_visible)
            self.checkbox_vars[f"{data_type.lower()}_{name}"] = var
            
            # Create the checkbox with a command that updates visibility
            cb = tk.Checkbutton(
                checkbox_frame, 
                text=name, 
                variable=var,
                command=lambda n=name, t=data_type.lower(), v=var: self.update_series_visibility(t, n, v.get())
            )
            cb.grid(row=i//3, column=i%3, sticky="w", padx=10, pady=3)

    def update_series_visibility(self, data_type, series_name, is_visible):
        """
        Update the visibility of a data series based on checkbox state.
        
        Args:
            data_type: Type of data (temperature, pressure, etc.)
            series_name: Name of the data series
            is_visible: Boolean indicating if series should be visible
        """
        # Get the dictionary for this data type
        data_dict = getattr(self.graph, f"{data_type}_dict")
        
        if series_name in data_dict:
            # If the current visibility state is different from the desired state
            if data_dict[series_name][1] != is_visible:
                # When turning off, add a discontinuity marker
                if not is_visible:
                    data_dict[series_name][2].append((None, None))
                
                # Update the visibility state
                data_dict[series_name][1] = is_visible

    def toggle_all_series(self, data_type, visible):
        """
        Set all series of a specific type to visible or invisible.
        
        Args:
            data_type: Type of data (temperature, pressure, etc.)
            visible: Boolean indicating if series should be visible
        """
        # Get the dictionary for this data type
        data_dict = getattr(self.graph, f"{data_type}_dict")
        
        # Update all series in this dictionary
        for name in data_dict:
            # Update the checkboxes
            checkbox_key = f"{data_type}_{name}"
            if checkbox_key in self.checkbox_vars:
                self.checkbox_vars[checkbox_key].set(visible)
            
            # Update the data visibility directly
            if data_dict[name][1] != visible and not visible:
                # Add discontinuity marker if hiding
                data_dict[name][2].append((None, None))
            
            # Set visibility
            data_dict[name][1] = visible

    def start_graph(self):
        """Start the graph plotting thread"""
        self.graph_thread = threading.Thread(
            target=self.graph.plot, 
            args=(self.plot_axes, self.canvas, plt.gcf())
        )
        self.graph_thread.daemon = True
        self.graph_thread.start()

    def toggle_graphing(self):
        """Toggle the graph plotting on/off"""
        self.graph_running = not self.graph_running
        
        if self.graph_running:
            self.graph.stop_plotting(False)
            self.graph_button.config(text="Stop Graphing", bg="light coral")
            # Restart the thread if it's stopped
            if not self.graph_thread.is_alive():
                self.start_graph()
        else:
            self.graph.stop_plotting(True)
            self.graph_button.config(text="Start Graphing", bg="pale green")

    def set_time_window(self):
        """Set the time window for the graph"""
        try:
            time_window = int(self.time_window_var.get())
            if time_window > 0:
                self.graph.set_time_window(time_window)
        except ValueError:
            # Handle invalid input
            self.time_window_var.set("120")  # Reset to default

    def export_graph_data(self):
        """Export graph data to CSV"""
        filename = self.graph.export_data()
        tk.messagebox.showinfo("Data Exported", f"Data exported to {filename}")

    def clear_graph_data(self):
        """Clear all graph data"""
        if tk.messagebox.askyesno("Clear Data", "Are you sure you want to clear all graph data?"):
            self.graph.clear_data()

    # pumps
    def create_pump_ui(self):
        """Creates UI elements for pumps."""
        frame = tk.Frame(self.equipment_frame)
        tk.Label(frame, text="Pumps", font=("Arial", 16, "underline")).grid(sticky="w", row=0, column=0)

        # Column headers
        headers = ["Connect", "Channel Number", "On", "Off", "Flow_Rate", "Set Flow_Rate"]
        for col, text in enumerate(headers, start=1):
            tk.Label(frame, text=text, font=("Arial", 12, "bold")).grid(row=1, column=col)

        for i, pump_name in enumerate(self.pumps_list):
            tk.Label(frame, text=pump_name).grid(row=i + 2, column=0, sticky="w")

            # Create buttons and entry fields
            connect_btn = tk.Button(frame, text="Disconnected", width=12, command=lambda i=i: self.pump_connect(i))
            channel_var = tk.StringVar()
            channel_entry = tk.Entry(frame, textvariable=channel_var, width=5)
            on_btn = tk.Button(frame, text="On", width=7, command=lambda i=i: self.pump_on(i))
            off_btn = tk.Button(frame, text="Off", width=7, command=lambda i=i: self.pump_off(i))
            flow_var = tk.StringVar()
            flow_entry = tk.Entry(frame, textvariable=flow_var, width=15)
            set_flow_btn = tk.Button(frame, text="Set", width=5, command=lambda i=i: self.pump_set_flow_rate(i))

            # Store elements in the dictionary
            self.pump_controls[i] = PumpControl(connect_btn, on_btn, off_btn, channel_var, flow_var)

            # Place elements in the grid
            connect_btn.grid(row=i + 2, column=1, padx=10)
            channel_entry.grid(row=i + 2, column=2, padx=10)
            on_btn.grid(row=i + 2, column=3, padx=10)
            off_btn.grid(row=i + 2, column=4, padx=10)
            flow_entry.grid(row=i + 2, column=5, padx=10)
            set_flow_btn.grid(row=i + 2, column=6)

        frame.pack(anchor="nw", padx=15, pady=15)

    def update_button_colors(self, pump_index, state):
        """Updates UI button colors for a given pump."""
        pump = self.pump_controls[pump_index]

        if state == "on":
            pump.on_button.config(bg="pale green")
            pump.off_button.config(bg="SystemButtonFace")
        elif state == "off":
            pump.off_button.config(bg="IndianRed1")
            pump.on_button.config(bg="SystemButtonFace")
        elif state == "connected":
            pump.connect.config(bg="LightSkyBlue1", text="Connected")
        elif state == "disconnected":
            pump.connect.config(bg="SystemButtonFace", text="Disconnected")

    def pump_connect(self, pump_index):
        """Handles connecting/disconnecting a pump."""
        pump = self.pump_controls[pump_index]

        if not self.pump_connect_vars[pump_index]:  # If not connected
            if not self.pump_port_vars[pump_index]:
                print("Please enter a port number.")
                return
            
            self.pump_connect_vars[pump_index] = True
            self.update_button_colors(pump_index, "connected")

            com_number = str(self.pump_port_vars[pump_index].get())
            pump_ser = Pump(com_number)
            pump_ser.set_independent_channel_control()
            pump.set_serial_obj(pump_ser)

        else:  # If already connected
            self.pump_connect_vars[pump_index] = False
            self.update_button_colors(pump_index, "disconnected")

            pump_ser = pump.serial_obj
            del pump_ser # equivalent to pump_ser.close()

    def pump_on(self, pump_index):
        """Turns on the pump if connected."""
        if not self.pump_connect_vars[pump_index]:
            return  # Ignore if pump is not connected

        self.update_button_colors(pump_index, "on")
        pump = self.pump_controls[pump_index]
        pump_ser = pump.serial_obj
        channel_number = int(pump.channel_var.get())

        pump_ser.start_channel(channel_number)

    def pump_off(self, pump_index):
        """Turns off the pump if connected."""
        if not self.pump_connect_vars[pump_index]:
            return  # Ignore if pump is not connected

        self.update_button_colors(pump_index, "off")
        pump = self.pump_controls[pump_index]
        pump_ser = pump.serial_obj
        channel_number = int(pump.channel_var.get())

        pump_ser.stop_channel(channel_number)

    def pump_set_flow_rate(self, pump_index):
        """Sets the flow rate for the pump."""
        if not self.pump_connect_vars[pump_index]:
            return  # Ignore if not connected

        pump = self.pump_controls[pump_index]
        pump_ser = pump.serial_obj
        channel_num = int(pump.channel_var.get())
        flow_rate = float(pump.flow_var.get())

        pump_ser.set_speed(channel_num, flow_rate)
        
        # Update the graph with the new 
        self.graph.update_dict("flow_rate", self.pumps_list[pump_index], flow_rate)

    # other
    def create_equipment_section(self, title, items, connect_command, display_current=False, entry=False, onoff_buttons=False):
        frame = tk.Frame(self.equipment_frame)
        tk.Label(self.equipment_frame, text=title, font=("Arial", 16, "underline")).pack(anchor="nw", padx=15, pady=(10, 0))
        if display_current or entry:
            self.equipment_data[title] = {}
        self.register_dictionary[title] = {}
        
        for i, name in enumerate(items):
            tk.Label(frame, text=name).grid(row=i + 1, column=0, sticky="w", pady=5)
            if display_current: # Temperatures and pressure trasmitters // read float class
                current_label = tk.Label(frame, text='', bg="white", borderwidth=1, relief="raised", width=10)
                current_label.grid(row=i + 1, column=1, padx=15)
                self.equipment_data[title][name] = current_label
                address = addresses[title][i]
                self.register_dictionary[title][name] = tk.IntVar(value=address)

                # connnect button for these two equipments
                connect_button = tk.Button(frame, text="Connect", font=("Arial", 12, "bold"), width=12, command=connect_command)
                connect_button.grid(row=0, column=0)
                self.connect_dictionary["buttons"][title] = connect_button
                self.connect_dictionary["vars"][title] = 0

            if entry: # Pressure regulators and stirrers
                var = tk.StringVar(value="0")
                entry_field = tk.Entry(frame, textvariable=var)
                entry_field.grid(row=i + 1, column=1, padx=15, pady=5)
                self.equipment_data[title][name] = var
                (tk.Button(frame, text="Enter",
                          command=lambda t=title, n=name, v=var: self.write_float_values(t, n, float(v.get()))
                           ).grid(row=i + 1, column=2)
                 )
                address = addresses[title][i]
                self.register_dictionary[title][name] = tk.IntVar(value=address)
                
            if onoff_buttons: # Pressure in/outs and valves
                tk.Button(frame, text="On", width=10, command=lambda t=title, n=name: self.toggle_onoff(t, n, True)).grid(row=i + 1, column=1, padx=15)
                tk.Button(frame, text="Off", width=10, command=lambda t=title, n=name: self.toggle_onoff(t, n, False)).grid(row=i + 1, column=2, padx=15)
                address = addresses[title][i]
                self.register_dictionary[title][name] = tk.IntVar(value=address)
        
        frame.pack(anchor="nw", padx=15)

    def create_temperatures_section(self):
        self.temperatures_list = ["Temperature 1", "Temperature 2", "Temperature 3"]
        self.create_equipment_section("Temperatures", self.temperatures_list, self.temperature_connect, display_current=True)
        
    def create_pressure_transmitter_section(self):
        self.pressure_transmitters_list = ["Pressure Transmitter 1", "Pressure Transmitter 2", "Pressure Transmitter 3"]
        self.create_equipment_section("Pressure Transmitters", self.pressure_transmitters_list, self.pressure_transmitter_connect, display_current=True)

    def create_pressure_regulator_section(self):
        self.pressure_regulators_list = ["Pressure Regulator 1", "Pressure Regulator 2"]
        self.create_equipment_section("Pressure Regulators", self.pressure_regulators_list, self.pressure_regulator_connect, entry=True)

    def create_pressure_inout_section(self):
        self.pressure_inouts_list = ["Pressure 1 In", "Pressure 1 Out", "Pressure 2 In", "Pressure 2 Out", "Pressure 3 In", "Pressure 3 Out"]
        self.create_equipment_section("Pressure In/Outs", self.pressure_inouts_list, self.pressure_inout_connect, onoff_buttons=True)
    
    def create_valves_section(self):
        self.valves_list = ["Valve 1"]
        self.create_equipment_section("Valves", self.valves_list, self.valve_connect, onoff_buttons=True)

    def create_stirrer_section(self):
        self.stirrers_list = ["10mL Stirrer", "5mL Stirrer", "40mL Stirrer"]
        self.create_equipment_section("Stirrers", self.stirrers_list, self.stirrer_connect, entry=True)
    
    def create_drum_section(self):
        self.drums_list = ["Drum 1"]
        self.create_equipment_section("Drums", self.drums_list, self.drum_connect, onoff_buttons=True)

    def toggle_connection(self, device_name, plc, read_float=False, plc_object=None, data_type = None):
        """
        Generic method to handle connection toggling for various devices.
        :param device_name: String name of the device for debugging purposes.
        :param connect_var: Tkinter IntVar tracking connection state.
        :param connect_button: Tkinter Button to update UI.
        :param plc: The PLC object handling the device connection.
        :param read_float: Boolean indicating whether to read float values.
        :param read_type: String type of data to read if read_float is True.
        """
        connect_button =  self.connect_dictionary["buttons"][device_name]
        connect_var = self.connect_dictionary["vars"][device_name]

        if connect_var == 0:  # If not connected, connect
            connect_button.config(bg="pale green", text="Connected")
            self.connect_dictionary["vars"][device_name] = 1
            plc.connect()
            if read_float:
                plc.reading_onoff(True)
                self.read_float_values(plc_object, data_type)
        else:  # If connected, disconnect
            self.connect_dictionary["vars"][device_name] = 0
            connect_button.config(bg="SystemButtonFace", text="Connect")
            if read_float:
                plc.reading_onoff(False)
            plc.disconnect()

    def temperature_connect(self):
        self.toggle_connection("Temperatures", self.temperature_plc, read_float=True, 
                               plc_object=self.temperature_plc, data_type="Temperatures")

    def pressure_transmitter_connect(self):
        self.toggle_connection("Pressure Transmitters", self.pressure_transmitter_plc, 
                               read_float=True, plc_object=self.pressure_transmitter_plc, 
                               data_type="Pressure Transmitters")

    def valve_connect(self):
        self.toggle_connection("Valves", self.valve_plc)

    def pressure_inout_connect(self):
        self.toggle_connection("Pressure In/Outs", self.pressure_inout_plc)

    def pressure_regulator_connect(self):
        self.toggle_connection("Pressure Regulators", self.pressure_regulator_plc)

    def stirrer_connect(self):
        self.toggle_connection("Stirrers", self.stirrer_plc)

    def drum_connect(self):
        self.toggle_connection("Drums", self.drum_plc)
    
    def create_assignment_section(self, title, headers, items):
        frame = tk.Frame(self.scrollable_frame)
        tk.Label(frame, text=title, font=("Arial", 12, "bold")).pack(pady=5)

        table_frame = tk.Frame(frame)
        for col, header in enumerate(headers):
            tk.Label(table_frame, text=header, font=("TkDefaultFont", 9, "underline")).grid(row=0, column=col, padx=5)

        for i, item in enumerate(items):
            tk.Label(table_frame, text=item).grid(row=i + 1, column=0, padx=5)
            
            # for j, var in enumerate(self.register_dictionary[title]):
            entry = tk.Entry(table_frame, textvariable=self.register_dictionary[title][item])
            entry.grid(row=i + 1, column=1, padx=5)

        table_frame.pack()
        frame.pack(pady=10)
    
    def open_assign(self):
        self.assign_page = tk.Toplevel(self.root)
        self.assign_page.title("Assign Equipment")

        # Create a canvas with scrollbars
        canvas = tk.Canvas(self.assign_page)
        scrollbar_y = tk.Scrollbar(self.assign_page, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_y.set)

        tk.Label(self.scrollable_frame, text="Assign Equipment", font=("Arial", 14, "bold")).pack(pady=10)
        
        tk.Label(self.scrollable_frame, text="Assign Pump Types and Ports", font=("Arial", 12, "bold")).pack(pady=5)
        pump_frame = tk.Frame(self.scrollable_frame)

        tk.Label(pump_frame, text="Pump Name", font=("TkDefaultFont", 9, "underline")).grid(row=0, column=0)
        tk.Label(pump_frame, text="Pump Port Number", font=("TkDefaultFont", 9, "underline")).grid(row=0, column=1)

        for i, name in enumerate(self.pumps_list):
            tk.Label(pump_frame, text=name).grid(row=i + 1, column=0, padx=5)

            address = addresses["Pumps"][i]
            self.pump_port_var = tk.IntVar(value=address)
            if self.pump_port_vars[i]:
                self.pump_port_var.set(self.pump_port_vars[i].get())
            pump_port_entry = tk.Entry(pump_frame, textvariable=self.pump_port_var)
            pump_port_entry.grid(row=i + 1, column=1, padx=5)
            self.pump_port_vars[i] = self.pump_port_var

        pump_frame.pack(pady=10)

        self.create_assignment_section(
            title="Temperatures",
            headers=["Name", "Register 1"],
            items=self.temperatures_list
        )

        self.create_assignment_section(
            title="Pressure Transmitters",
            headers=["Name", "Register 1"],
            items=self.pressure_transmitters_list
        )

        self.create_assignment_section(
            title="Pressure Regulators",
            headers=["Name", "Register 1"],
            items=self.pressure_regulators_list
        )

        self.create_assignment_section(
            title="Pressure In/Outs",
            headers=["Name", "Address"],
            items=self.pressure_inouts_list
        )

        self.create_assignment_section(
            title="Valves",
            headers=["Name", "Address"],
            items=self.valves_list
        )

        self.create_assignment_section(
            title="Stirrers",
            headers=["Name", "Register 1"],
            items=self.stirrers_list
        )

        self.create_assignment_section(
            title="Drums",
            headers=["Name", "Register 1"],
            items=self.drums_list
        )

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")

    def read_float_values(self, plc_object, data_type):
        """
        For PLC equipment that reads float values
        data_type is the type of equipment (i.e. Temperatures or Pressure Transmitters)
        """
        for equipment_name in self.equipment_data[data_type]:
            label = self.equipment_data[data_type][equipment_name]
            reg1 = self.register_dictionary[data_type][equipment_name].get()

            # Create a custom function to update both the label and the graph
            def update_value_and_graph(label, equipment_name, data_type):
                def _update(value):
                    # Update the label
                    label.config(text=str(value))
                    # Update the graph data
                    data_type_lower = data_type.lower()
                    if data_type_lower == "pressure transmitters":
                        data_type_lower = "pressures"  # dictionary name is pressures_dicts
                    self.graph.update_dict(data_type_lower, equipment_name, value)
                return _update

            callback = update_value_and_graph(label, equipment_name, data_type)
            
            # Modified to pass our custom callback function that updates both UI and graph
            t = threading.Thread(target=lambda: plc_object.read_float(callback, reg1, reg1+1))
            t.daemon = True
            t.start()
    
    def exit_shortcut(self, event):
        """Exit the GUI when the escape key is pressed."""
        if event.keysym == "Escape":
            self.root.quit()
    
    def on_closing(self):
        """Handle window close event (X button)"""
        if hasattr(self, 'graph'):
            self.graph.stop_plotting(True)  # Stop the plot thread
        
        if hasattr(self, 'testing') and self.testing:
            self.testing = False  # Stop the test data thread if running
        
        # Wait briefly for threads to terminate
        import time
        time.sleep(0.2)
        
        self.root.destroy()  # Destroy the Tkinter root window
        import sys
        sys.exit(0)  # Force exit the Python process

    def test(self):

        pass

gui = System2()