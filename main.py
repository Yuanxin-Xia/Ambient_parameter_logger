from tkinter import StringVar, Text, Tk, ttk, filedialog, messagebox
from serial import Serial, tools
import serial.tools.list_ports
from threading import Thread
from csv import writer as csvwriter
import os.path as ospath
from time import strftime, sleep
from math import sqrt

class SerialCSVLogger:
    def __init__(self, root):
        self.root = root
        self.root.title("Ambient parameter recorder by Yuanxin Xia")

        self.ser = None
        self.read_thread = None
        self.running = False

        # CSV file path
        self.csv_file_path = StringVar(value="")

        # Port & baud
        self.selected_port = StringVar(value="")
        self.selected_baud = StringVar(value="115200")

        # Interval (ms)
        self.interval_var = StringVar(value="5000")  # default 5s

        # ------------- Online stats for T, H, P -------------
        # Each parameter has count, mean, M2 (for variance calc)
        self.t_count = 0
        self.t_mean = 0.0
        self.t_M2 = 0.0

        self.h_count = 0
        self.h_mean = 0.0
        self.h_M2 = 0.0

        self.p_count = 0
        self.p_mean = 0.0
        self.p_M2 = 0.0
        # ---------------------------------------------------

        # Build UI
        self.create_widgets()
        self.list_serial_ports()

    def create_widgets(self):
        # --- Serial Settings Frame ---
        frame_serial = ttk.LabelFrame(self.root, text="Serial Settings")
        frame_serial.pack(padx=10, pady=10, fill="x")

        ttk.Label(frame_serial, text="Port:").grid(row=0, column=0, padx=5, pady=5, sticky="E")
        self.port_combo = ttk.Combobox(frame_serial, textvariable=self.selected_port, width=30)
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)

        self.refresh_button = ttk.Button(frame_serial, text="Refresh", command=self.list_serial_ports)
        self.refresh_button.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(frame_serial, text="Baud:").grid(row=0, column=3, padx=5, pady=5, sticky="E")
        self.baud_combo = ttk.Combobox(
            frame_serial, textvariable=self.selected_baud,
            values=["9600", "19200", "38400", "57600", "115200", "230400"],
            width=10
        )
        self.baud_combo.grid(row=0, column=4, padx=5, pady=5)
        self.baud_combo.current(4)

        # --- Interval Settings ---
        frame_interval = ttk.LabelFrame(self.root, text="Interval Settings")
        frame_interval.pack(padx=10, pady=10, fill="x")

        ttk.Label(frame_interval, text="Interval (ms):").grid(row=0, column=0, padx=5, pady=5, sticky="E")
        self.interval_entry = ttk.Entry(frame_interval, textvariable=self.interval_var, width=15)
        self.interval_entry.grid(row=0, column=1, padx=5, pady=5)

        # --- CSV Settings Frame ---
        frame_csv = ttk.LabelFrame(self.root, text="File saving setting")
        frame_csv.pack(padx=10, pady=10, fill="x")

        ttk.Label(frame_csv, text="CSV Path:").grid(row=0, column=0, padx=5, pady=5, sticky="E")
        self.csv_entry = ttk.Entry(frame_csv, textvariable=self.csv_file_path, width=40)
        self.csv_entry.grid(row=0, column=1, padx=5, pady=5)
        self.browse_button = ttk.Button(frame_csv, text="Browse...", command=self.browse_csv_file)
        self.browse_button.grid(row=0, column=2, padx=5, pady=5)

        # --- Control Buttons ---
        frame_buttons = ttk.Frame(self.root)
        frame_buttons.pack(padx=10, pady=5, fill="x")

        self.start_button = ttk.Button(frame_buttons, text="Start Logging", command=self.start_logging)
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(frame_buttons, text="Stop Logging", command=self.stop_logging)
        self.stop_button.pack(side="left", padx=5)

        # --- Log Text ---
        self.log_text = Text(self.root, height=10, width=60)
        self.log_text.pack(padx=10, pady=10, fill="both", expand=True)

    def list_serial_ports(self):
        ports = list(tools.list_ports.comports())
        display_list = []
        auto_index = None

        # Common keywords for ESP32 or Arduino clones
        keywords = ["CH340", "CP210", "CH9102", "USB", "SILICON"]

        for i, p in enumerate(ports):
            text = f"{p.device} ({p.description})"
            display_list.append(text)
            # Try to auto-select if it matches a known keyword
            upper_desc = p.description.upper()
            if any(k in upper_desc for k in keywords):
                auto_index = i

        self.port_combo['values'] = display_list
        if auto_index is not None:
            self.port_combo.current(auto_index)
        elif display_list:
            self.port_combo.current(0)

    def browse_csv_file(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV File", "*.csv"), ("All Files", "*.*")]
        )
        if file_path:
            self.csv_file_path.set(file_path)

    def start_logging(self):
        if self.running:
            messagebox.showwarning("Warning", "Logging is already running.")
            return

        selected_text = self.selected_port.get().strip()
        if "(" in selected_text:
            port = selected_text.split("(")[0].strip()
        else:
            port = selected_text

        baud_str = self.selected_baud.get().strip()
        if not port:
            messagebox.showerror("Error", "Please select a serial port.")
            return
        if not baud_str.isdigit():
            messagebox.showerror("Error", "Baud rate must be numeric.")
            return

        csv_path = self.csv_file_path.get().strip()
        if not csv_path:
            messagebox.showerror("Error", "Please select a CSV file path.")
            return

        # Open the serial port
        try:
            self.ser = Serial(port, int(baud_str), timeout=1)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open port {port}:\n{e}")
            return

        # If new file, write header
        new_file = not ospath.exists(csv_path)
        if new_file:
            try:
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    w = csvwriter(f)
                    w.writerow(["Time", "Temperature", "Humidity", "Pressure"])
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create CSV file:\n{e}")
                self.ser.close()
                self.ser = None
                return

        # Send the "GAP,<interval>" command
        interval_str = self.interval_var.get().strip()
        if interval_str.isdigit():
            cmd = f"GAP,{interval_str}\n"
            self.ser.write(cmd.encode("utf-8"))
            self.log_text.insert("end", f"Sent interval command: {cmd}")
            self.log_text.see("end")
        else:
            self.log_text.insert("end", "Warning: Interval is not numeric, skipping GAP command.\n")
            self.log_text.see("end")

        # Reset stats counters before new logging session
        self.reset_stats()

        # Start background reading
        self.running = True
        self.read_thread = Thread(target=self.read_serial_data, args=(csv_path,), daemon=True)
        self.read_thread.start()

        self.log_text.insert("end", f"[{strftime('%H:%M:%S')}] Port {port} opened. Logging started.\n")
        self.log_text.see("end")

    def stop_logging(self):
        if not self.running:
            return
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.log_text.insert("end", f"[{strftime('%H:%M:%S')}] Logging stopped. Port closed.\n")
        self.log_text.see("end")

        # After stopping, compute and print final statistics
        self.print_final_stats()

    def read_serial_data(self, csv_path):
        while self.running:
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    # e.g. "DATA,25.30,55.32,101825.32"
                    if line.startswith("DATA,"):
                        parts = line.split(",")
                        if len(parts) == 4:
                            timestamp_str = strftime("%Y-%m-%d %H:%M:%S")
                            try:
                                temp = float(parts[1])
                                humi = float(parts[2])
                                pres = float(parts[3])
                            except ValueError:
                                continue
                            # Write to CSV
                            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                                w = csvwriter(f)
                                w.writerow([timestamp_str, temp, humi, pres])
                            # Show in log text
                            self.log_text.insert("end", f"{timestamp_str}, T={temp}, H={humi}, P={pres}\n")
                            self.log_text.see("end")

                            # Update online stats
                            self.update_stats_temp(temp)
                            self.update_stats_humi(humi)
                            self.update_stats_pres(pres)
                        else:
                            # Could be "DATA,ERROR" or any other format
                            self.log_text.insert("end", line + "\n")
                            self.log_text.see("end")
                    else:
                        # Possibly "Interval updated to: 5000 ms" or other messages
                        self.log_text.insert("end", line + "\n")
                        self.log_text.see("end")
                else:
                    sleep(0.01)
            except Exception as e:
                self.log_text.insert("end", f"Error: {e}\n")
                self.log_text.see("end")
                sleep(0.5)

        if self.ser and self.ser.is_open:
            self.ser.close()

    # --------------------------
    # Online Stats Methods
    # --------------------------
    def reset_stats(self):
        """Reset counters for a new logging session."""
        self.t_count = 0
        self.t_mean = 0.0
        self.t_M2 = 0.0

        self.h_count = 0
        self.h_mean = 0.0
        self.h_M2 = 0.0

        self.p_count = 0
        self.p_mean = 0.0
        self.p_M2 = 0.0

    def update_stats_temp(self, x):
        # Welford for temperature
        self.t_count += 1
        delta = x - self.t_mean
        self.t_mean += delta / self.t_count
        delta2 = x - self.t_mean
        self.t_M2 += delta * delta2

    def update_stats_humi(self, x):
        # Welford for humidity
        self.h_count += 1
        delta = x - self.h_mean
        self.h_mean += delta / self.h_count
        delta2 = x - self.h_mean
        self.h_M2 += delta * delta2

    def update_stats_pres(self, x):
        # Welford for pressure
        self.p_count += 1
        delta = x - self.p_mean
        self.p_mean += delta / self.p_count
        delta2 = x - self.p_mean
        self.p_M2 += delta * delta2

    def print_final_stats(self):
        """Compute final average/std dev and print them in the log text."""
        # Temperature
        if self.t_count > 1:
            t_var = self.t_M2 / (self.t_count - 1)
            t_std = sqrt(t_var)
            self.log_text.insert(
                "end",
                f"Temperature: count={self.t_count}, mean={self.t_mean:.2f}, std={t_std:.2f}\n"
            )
        elif self.t_count == 1:
            self.log_text.insert(
                "end",
                f"Temperature: count=1, mean={self.t_mean:.2f}, std=0.00 (only one sample)\n"
            )
        else:
            self.log_text.insert("end", "No temperature data recorded.\n")

        # Humidity
        if self.h_count > 1:
            h_var = self.h_M2 / (self.h_count - 1)
            h_std = sqrt(h_var)
            self.log_text.insert(
                "end",
                f"Humidity: count={self.h_count}, mean={self.h_mean:.2f}, std={h_std:.2f}\n"
            )
        elif self.h_count == 1:
            self.log_text.insert(
                "end",
                f"Humidity: count=1, mean={self.h_mean:.2f}, std=0.00 (only one sample)\n"
            )
        else:
            self.log_text.insert("end", "No humidity data recorded.\n")

        # Pressure
        if self.p_count > 1:
            p_var = self.p_M2 / (self.p_count - 1)
            p_std = sqrt(p_var)
            self.log_text.insert(
                "end",
                f"Pressure: count={self.p_count}, mean={self.p_mean:.2f}, std={p_std:.2f}\n"
            )
        elif self.p_count == 1:
            self.log_text.insert(
                "end",
                f"Pressure: count=1, mean={self.p_mean:.2f}, std=0.00 (only one sample)\n"
            )
        else:
            self.log_text.insert("end", "No pressure data recorded.\n")

        self.log_text.see("end")

def main():
    root = Tk()
    app = SerialCSVLogger(root)
    root.mainloop()

if __name__ == "__main__":
    main()
