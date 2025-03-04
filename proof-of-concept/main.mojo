"""
Arduino LED controller with music reactivity
"""

from python import Python, PythonObject
import time
import math


fn run_pulse_effect(
    handler: PythonObject, speed: Float64, duration: Float64 = 10.0
) raises:
    """Run a pulsing light effect at the specified speed for specified duration.
    """
    print("Running pulse effect for", duration, "seconds")

    # Use sine wave for smooth pulsing
    var start_time = time.perf_counter()
    var end_time = start_time + duration

    try:
        while time.perf_counter() < end_time:
            var current_time = time.perf_counter() - start_time
            # Map sine wave (-1 to 1) to brightness (0 to 1)
            var angle = current_time * speed * 6.28  # speed * 2π
            var brightness = (math.sin(angle) + 1) / 2  # Map to 0.0-1.0

            # Send to Arduino
            handler.send_value(brightness)

            # Small delay to avoid flooding Arduino
            time.sleep(0.03)

        # Turn off LED when done
        handler.send_value(0.0)
        print("Pulse effect completed")
    except:
        print("Pulse effect interrupted")
        handler.send_value(0.0)  # Turn off LED


fn main() raises:
    print("Arduino LED Control")
    print("------------------")

    # Initialize Python modules
    var serial_module = Python.import_module("serial_handler")
    var audio_module = Python.import_module("audio_processor")

    # Create instances
    var serial_handler = serial_module.SerialHandler()
    var audio_processor = audio_module.AudioProcessor()

    # Connect to Arduino
    var result = serial_handler.connect()
    if not Bool(result[0]):
        print("Failed to connect to Arduino")
        return

    print(String(result[1]))
    print("\nCommands:")
    print("  <float>  - Set value (0.0-1.0) for LED brightness")
    print("  music    - Start music-reactive mode")
    print("  stop     - Stop music-reactive mode")
    print("  sens <value> - Set music sensitivity (0.0-1.0)")
    print("  pulse <speed> [duration] - Run pulse effect (speed in Hz)")
    print("  exit     - Exit the program")

    # Define beat callback function in Python
    var callbacks = Python.import_module("callbacks")
    var on_beat = callbacks.create_beat_callback(serial_handler)

    var running = True
    while running:
        print("> ", end="")
        var input_str = input()

        if input_str.lower() == "exit":
            running = False
            continue

        # Add this to your main.mojo command processor:
        if input_str == "beat":
            print("Manually triggering beat...")
            # Trigger a test beat with energy 0.8
            on_beat(0.8)
            continue

        if input_str == "music":
            var response = audio_processor.start_listening(on_beat)
            print(String(response))
            continue

        if input_str == "stop":
            var response = audio_processor.stop_listening()
            print(String(response))
            continue

        if input_str.startswith("sens "):
            try:
                var value = Float64(input_str[5:])
                if value < 0.0 or value > 1.0:
                    print("Sensitivity must be between 0.0 and 1.0")
                    continue

                var response = audio_processor.set_sensitivity(value)
                print(String(response))
                continue
            except:
                print("Invalid sensitivity value")
                continue

        if input_str.startswith("pulse "):
            try:
                var parts = input_str[6:].split()
                var speed = Float64(parts[0])

                # Optional duration parameter, default 10 seconds
                var duration = 10.0
                if len(parts) > 1:
                    duration = Float64(parts[1])

                if speed <= 0:
                    print("Speed must be positive")
                    continue

                run_pulse_effect(serial_handler, speed, duration)
                continue
            except:
                print("Invalid format. Use: pulse <speed> [duration]")
                continue

        # Normal brightness value input
        try:
            var value = Float64(input_str)
            if value < 0.0 or value > 1.0:
                print("Value must be between 0.0 and 1.0")
                continue

            # Send the value to Arduino
            serial_handler.send_value(value)

        except:
            print(
                "Invalid input. Enter a number between 0.0 and 1.0, or type"
                " 'help'"
            )

    # Clean up
    audio_processor.stop_listening()
    serial_handler.close()
    print("Connection closed.")
