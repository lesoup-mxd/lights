"""
Arduino connection example using Mojo's Serial communication.

This example demonstrates how to establish a connection with an Arduino,
send commands, and read responses.
"""

from src.serial import Serial
import time


fn main() raises:
    print("Arduino Connection Example")

    # Arduino typically connects on /dev/ttyACM0 or /dev/ttyUSB0
    # You may need to change this path based on your system
    var port_paths = List("/dev/ttyACM0", "/dev/ttyUSB0", "/dev/ttyACM1")
    var connected = False
    var arduino = Serial("", baudrate=9600)  # Placeholder initialization

    # Try to connect to Arduino on different possible ports
    for _path in range(len(port_paths)):
        path = port_paths[_path]
        print("Attempting to connect to Arduino on " + path + "...")
        arduino = Serial(path, baudrate=9600, timeout=2.0)
        try:
            arduino.s_open()

            # Wait for Arduino to reset after establishing connection
            time.sleep(2.0)

            # Send a test command to verify connection
            _ = arduino.s_write("PING\n")
            time.sleep(0.1)

            # Read the response (timeout after 2 seconds)
            var response = arduino.s_readline()

            if len(response) > 0:
                print("Connected to Arduino on " + path)
                print("Arduino response: " + response)
                connected = True
                break
            else:
                print("No response from device on " + path)
                arduino.s_close()
        except:
            print("Failed to connect on " + path)
            # Continue to the next port

    if not connected:
        print("Could not connect to Arduino. Please check:")
        print("  - Arduino is connected to the computer")
        print("  - Correct port is being used")
        print("  - Arduino has appropriate firmware that responds to 'PING'")
        return

    # Main communication loop
    try:
        print("\nArduino Communication Started")
        print("Send commands to Arduino. Type 'exit' to quit.")

        while True:
            print("> ", end="")
            var command = input()

            if command == "exit":
                break

            # Add newline if not present
            if not command.endswith("\n"):
                command += "\n"

            # Send command to Arduino
            _ = arduino.s_write(command)
            time.sleep(0.1)  # Give Arduino time to process

            # Read response
            var response = arduino.s_readline()
            print("Arduino: " + response)

    except:
        print("Error during communication")
    finally:
        # Close the connection
        if connected:
            print("Closing connection...")
            arduino.s_close()
            print("Connection closed.")
