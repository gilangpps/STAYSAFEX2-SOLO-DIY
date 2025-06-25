import serial
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import numpy as np
from datetime import datetime
import queue
import threading

class RadiationMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Medical X-ray Radiation Monitoring System")
        self.root.geometry("1000x600")
        
        # Initialize data structures
        self.time_data = []
        self.voltage_data = []
        self.dose_data = []
        self.pulse_count = 0
        self.is_running = False
        self.serial_connected = False
        self.data_queue = queue.Queue()
        self.ser = None
        
        # Create main figures
        self.fig_voltage = plt.Figure(figsize=(8, 4), dpi=100)
        self.ax_voltage = self.fig_voltage.add_subplot(111)
        
        # Create dose window and figure
        self.dose_window = None
        self.fig_dose = plt.Figure(figsize=(8, 4), dpi=100)
        self.ax_dose = self.fig_dose.add_subplot(111)
        
        self.setup_plots()
        self.setup_ui()
        
        # Initialize serial thread
        self.serial_thread = None

    def setup_ui(self):
        # Configure style
        style = ttk.Style()
        style.configure('TFrame', background='#e1f5fe')
        style.configure('TButton', font=('Helvetica', 10), padding=5)
        style.configure('TLabel', background='#e1f5fe', font=('Helvetica', 10))
        style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))
        
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="X-RAY RADIATION MONITOR", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Show Dose Window", command=self.show_dose_window).pack(side=tk.RIGHT, padx=5)
        
        # Control panel
        control_frame = ttk.LabelFrame(main_frame, text="System Control")
        control_frame.pack(fill=tk.X, pady=5)
        
        # Connection controls
        conn_frame = ttk.Frame(control_frame)
        conn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(conn_frame, text="COM Port:").pack(side=tk.LEFT, padx=5)
        self.com_port = ttk.Combobox(conn_frame, values=self.get_serial_ports(), width=10)
        self.com_port.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(conn_frame, text="Connect", command=self.connect_serial).pack(side=tk.LEFT, padx=5)
        ttk.Button(conn_frame, text="Disconnect", command=self.disconnect_serial).pack(side=tk.LEFT, padx=5)
        
        # Monitoring controls
        monitor_frame = ttk.Frame(control_frame)
        monitor_frame.pack(fill=tk.X, pady=5)
        
        self.start_btn = ttk.Button(monitor_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(monitor_frame, text="Stop Monitoring", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(monitor_frame, text="Save Data", command=self.save_data).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("System Ready")
        ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN).pack(fill=tk.X, pady=(10, 0))
        
        # Voltage plot frame
        voltage_frame = ttk.LabelFrame(main_frame, text="X-ray Signal Voltage")
        voltage_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.canvas_voltage = FigureCanvasTkAgg(self.fig_voltage, master=voltage_frame)
        self.canvas_voltage.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def show_dose_window(self):
        """Create a separate window for dose visualization"""
        if self.dose_window is None or not tk.Toplevel.winfo_exists(self.dose_window):
            self.dose_window = tk.Toplevel(self.root)
            self.dose_window.title("Accumulated Radiation Dose")
            self.dose_window.geometry("800x500")
            
            dose_frame = ttk.Frame(self.dose_window)
            dose_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            self.canvas_dose = FigureCanvasTkAgg(self.fig_dose, master=dose_frame)
            self.canvas_dose.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Update plot immediately
            self.update_dose_plot()
            
            # Handle window close
            self.dose_window.protocol("WM_DELETE_WINDOW", self.on_dose_window_close)
        else:
            self.dose_window.lift()

    def on_dose_window_close(self):
        """Handle dose window closing"""
        self.dose_window.destroy()
        self.dose_window = None

    def setup_plots(self):
        # Voltage plot setup
        self.ax_voltage.set_title('X-ray Signal Voltage', fontsize=10)
        self.ax_voltage.set_ylabel('Voltage (V)')
        self.ax_voltage.grid(True, linestyle='--', alpha=0.6)
        self.voltage_line, = self.ax_voltage.plot([], [], 'b-', label='Signal')
        self.threshold_line = self.ax_voltage.axhline(y=0.05, color='r', linestyle='--', label='Threshold')
        self.ax_voltage.legend()
        
        # Dose plot setup
        self.ax_dose.set_title('Accumulated Radiation Dose', fontsize=10)
        self.ax_dose.set_xlabel('Time (s)')
        self.ax_dose.set_ylabel('Dose (μSv)')
        self.ax_dose.grid(True, linestyle='--', alpha=0.6)
        self.dose_line, = self.ax_dose.plot([], [], 'r-', label='Dose')
        self.ax_dose.legend()

    def get_serial_ports(self):
        """Get list of available serial ports"""
        ports = ['COM%s' % (i + 1) for i in range(256)]
        available_ports = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                available_ports.append(port)
            except (OSError, serial.SerialException):
                pass
        return available_ports
    
    def connect_serial(self):
        port = self.com_port.get()
        if not port:
            messagebox.showerror("Error", "Please select a COM port")
            return
            
        try:
            self.ser = serial.Serial(port, 115200, timeout=1)
            self.serial_connected = True
            self.status_var.set(f"Connected to {port}")
            self.start_btn.config(state=tk.NORMAL)
            messagebox.showinfo("Success", f"Connected to {port}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to {port}: {str(e)}")
    
    def disconnect_serial(self):
        if self.ser and self.ser.is_open:
            self.stop_monitoring()
            self.ser.close()
            self.serial_connected = False
            self.status_var.set("Disconnected")
            messagebox.showinfo("Info", "Serial port disconnected")
    
    def start_monitoring(self):
        if not self.serial_connected:
            messagebox.showerror("Error", "Not connected to serial port")
            return
            
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_var.set("Monitoring in progress...")
        
        # Clear previous data
        self.time_data = []
        self.voltage_data = []
        self.dose_data = []
        self.pulse_count = 0
        
        # Start serial reading thread
        self.serial_thread = threading.Thread(target=self.read_serial_data, daemon=True)
        self.serial_thread.start()
        
        # Start plot updates
        self.update_voltage_plot()
        if self.dose_window:
            self.update_dose_plot()
    
    def stop_monitoring(self):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Monitoring stopped")
    
    def read_serial_data(self):
        while self.is_running and self.serial_connected:
            try:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8').strip()
                    if '|' in line:
                        parts = line.split('|')
                        if len(parts) == 4:
                            timestamp = int(parts[0])
                            voltage = float(parts[1])
                            pulse_count = int(parts[2])
                            dose = float(parts[3])
                            
                            self.data_queue.put((timestamp, voltage, pulse_count, dose))
            except Exception as e:
                print(f"Serial read error: {str(e)}")
                self.stop_monitoring()
    
    def update_voltage_plot(self):
        """Update only the voltage plot"""
        # Process data from queue
        self.process_queue_data()
        
        # Update voltage plot
        if self.time_data and self.voltage_data:
            self.voltage_line.set_data(self.time_data, self.voltage_data)
            self.ax_voltage.relim()
            self.ax_voltage.autoscale_view()
            self.fig_voltage.tight_layout()
            self.canvas_voltage.draw()
        
        # Update status
        if self.time_data:
            self.status_var.set(
                f"Monitoring | Time: {self.time_data[-1]:.1f}s | Voltage: {self.voltage_data[-1]:.4f}V | "
                f"Pulses: {self.pulse_count} | Dose: {self.dose_data[-1]:.6f}μSv"
            )
        
        # Schedule next update
        if self.is_running:
            self.root.after(100, self.update_voltage_plot)

    def update_dose_plot(self):
        """Update only the dose plot"""
        # Process data from queue
        self.process_queue_data()
        
        # Update dose plot
        if self.time_data and self.dose_data:
            self.dose_line.set_data(self.time_data, self.dose_data)
            self.ax_dose.relim()
            self.ax_dose.autoscale_view()
            self.fig_dose.tight_layout()
            self.canvas_dose.draw()
        
        # Schedule next update if window exists
        if self.is_running and self.dose_window and tk.Toplevel.winfo_exists(self.dose_window):
            self.dose_window.after(100, self.update_dose_plot)

    def process_queue_data(self):
        """Process data from the queue"""
        while not self.data_queue.empty():
            timestamp, voltage, pulse_count, dose = self.data_queue.get()
            
            self.time_data.append(timestamp / 1000.0)  # Convert to seconds
            self.voltage_data.append(voltage)
            self.dose_data.append(dose)
            self.pulse_count = pulse_count
            
            # Limit data points
            max_points = 200
            if len(self.time_data) > max_points:
                self.time_data.pop(0)
                self.voltage_data.pop(0)
                self.dose_data.pop(0)
    
    def save_data(self):
        if not self.time_data:
            messagebox.showwarning("Warning", "No data to save")
            return
            
        try:
            # Create DataFrame
            df = pd.DataFrame({
                'Time (s)': self.time_data,
                'Voltage (V)': self.voltage_data,
                'Dose (μSv)': self.dose_data,
                'Pulse Count': [self.pulse_count] * len(self.time_data)
            })
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"radiation_data_{timestamp}.xlsx"
            png_filename = f"radiation_plot_{timestamp}.png"
            
            # Save to Excel
            df.to_excel(excel_filename, index=False)
            
            # Save combined plot
            fig_combined = plt.Figure(figsize=(10, 8))
            ax1 = fig_combined.add_subplot(211)
            ax2 = fig_combined.add_subplot(212)
            
            ax1.plot(self.time_data, self.voltage_data, 'b-')
            ax1.set_ylabel('Voltage (V)')
            ax1.set_title('X-ray Signal Voltage')
            ax1.grid(True)
            
            ax2.plot(self.time_data, self.dose_data, 'r-')
            ax2.set_xlabel('Time (s)')
            ax2.set_ylabel('Dose (μSv)')
            ax2.set_title('Accumulated Radiation Dose')
            ax2.grid(True)
            
            fig_combined.tight_layout()
            fig_combined.savefig(png_filename)
            plt.close(fig_combined)
            
            messagebox.showinfo("Success", f"Data saved to:\n{excel_filename}\n{png_filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = RadiationMonitorApp(root)
    root.mainloop()
