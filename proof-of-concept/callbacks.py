def create_beat_callback(serial_handler):
    def on_beat(energy):
        # Scale brightness based on energy
        brightness = min(1.0, energy * 1.5)  # Amplify for visibility
        print(f"Beat! Setting LED to {brightness:.2f}")
        serial_handler.send_value(brightness)
        
        # Schedule a fade after beat
        import threading
        def fade():
            fade_val = brightness * 0.5
            print(f"Fading to {fade_val:.2f}")
            serial_handler.send_value(fade_val)
            
        threading.Timer(0.1, fade).start()
    return on_beat