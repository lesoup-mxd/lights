import time
from typing import List, Optional, Tuple, Union

import serial


class SerialHandler:
    """Handles serial communication with Arduino."""
    
    def __init__(self, port=None, baudrate=250000, timeout=2.0): #250000 max
        """Initialize the serial handler."""
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.connected = False
    
    def connect(self, ports=None) -> Tuple[bool, str]:
        """Try to connect to Arduino on various ports."""
        if not ports:
            # Default ports to try
            ports = ["/dev/ttyACM1","/dev/ttyACM0", "/dev/ttyUSB0"]
        
        for port in ports:
            try:
                print(f"Trying {port}...")
                self.ser = serial.Serial(port, self.baudrate, timeout=0.5)
                time.sleep(1)  # Give Arduino time to reset
                self.connected = True
                return True, f"Connected on {port}"
            except Exception as e:
                print(f"Failed: {e}")
        
        return False, "Could not connect to Arduino"
    
    def send_value(self, value):
        if not self.connected or not self.ser:
            return False
        
        # Format value with 3 decimal places
        command = f"{value:.3f}\n"
        self.ser.write(command.encode('utf-8'))
        return True
    
    def send_binary_sequence(self, values):
        """Send a sequence of values as binary data without any newlines."""
        if not self.connected or not self.ser:
            print("Error: Not connected")
            return False
        
        print(f"Sending {len(values)} binary values")
        
        # Convert to bytes - IMPORTANT: Send as raw bytes, not text
        count = len(values)
        
        # Create a bytearray for binary data
        data = bytearray()
        
        # Add count as 2 bytes (big endian)
        data.append((count >> 8) & 0xFF)  # High byte
        data.append(count & 0xFF)         # Low byte
        
        # Add each value as a single byte
        for val in values:
            # Convert 0.0-1.0 float to 0-255 byte value
            byte_val = int(max(0, min(1, val)) * 255)
            data.append(byte_val)
        
        # Send as raw binary - NO newlines or string conversion
        bytes_written = self.ser.write(data)
        self.ser.flush()  # Make sure all data is transmitted
        
        print(f"Sent {bytes_written} bytes (header: {data[0]},{data[1]}, count: {count})")
        return True
    
    def has_data(self):
        """Check if there is data available to read."""
        if not self.connected or not self.ser:
            return False
        try:
            return self.ser.in_waiting > 0
        except:
            print("Error checking for data")
            return False

    def read_line(self):
        """Read a line of text from the Arduino."""
        if not self.connected or not self.ser:
            return ""
        try:
            if self.ser.in_waiting > 0:
                return self.ser.readline().decode('utf-8').strip()
            return ""
        except Exception as e:
            print(f"Error reading line: {e}")
            return ""
    
    def close(self):
        """Close the serial connection."""
        if self.ser and self.connected:
            self.ser.close()
            self.connected = False

# Simple test function
def test_connection():
    handler = SerialHandler()
    success, msg = handler.connect()
    print(msg)
    
    if success:
        print("Setting value to 0.5...")
        handler.send_value(0.5)
        handler.close()

if __name__ == "__main__":
    test_connection()