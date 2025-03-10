import audioop
import threading
import time

import numpy as np
import pyaudio


class AudioProcessor:
    def __init__(self):
        # Audio processing parameters
        self.is_listening = False
        self.beat_detected = False
        self.energy_threshold = 1.1  # Multiplier above average energy
        self.sensitivity = 0.8      # 0.0-1.0, higher is more sensitive
        self.energy_history = []
        self.bass_history = []      # Added: track bass energy separately
        self.last_beat_time = 0
        self.min_beat_interval = 0.005  # Seconds between beats
        self.audio = None
        self.stream = None
        self.callback_fn = None
        self.lock = threading.Lock()
        
    def start_listening(self, callback_fn=None):
        """Start audio capture and beat detection"""
        if self.is_listening:
            return "Already listening"
        
        self.callback_fn = callback_fn
        self.is_listening = True
        self.energy_history = []
        self.bass_history = []      # Added: clear bass history
        
        # Initialize PyAudio
        self.audio = pyaudio.PyAudio()
        
        # Start audio stream
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            frames_per_buffer=1024,  # Increased for better frequency resolution
            stream_callback=self._audio_callback
        )
        print(f"Using device: {self.audio.get_default_input_device_info()['name']}")
        return "Audio processing started (bass-enhanced)"
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        if not self.is_listening:
            return (None, pyaudio.paContinue)
            
        # Convert audio data to numpy array for frequency analysis
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        
        # Calculate overall energy (RMS)
        rms = audioop.rms(in_data, 2)  # width=2 for paInt16
        energy = min(1.0, rms / 10000.0)  # Normalize to 0-1 range
        
        # Perform frequency analysis using FFT
        fft_data = np.abs(np.fft.rfft(audio_data))
        
        # Multi-band energy extraction:
        # 1. Bass (60-250Hz) - bins 1-6
        bass_bins = fft_data[1:7]
        bass_energy = min(1.0, np.sum(bass_bins) / 40000000.0)
        
        # 2. Mid-range (500Hz-2kHz) - bins ~12-46
        mid_bins = fft_data[12:47]
        mid_energy = min(1.0, np.sum(mid_bins) / 100000000.0)
        
        # 3. High-range (5kHz-15kHz) - bins ~115-350
        high_bins = fft_data[115:350]
        high_energy = min(1.0, np.sum(high_bins) / 50000000.0)
        
        # Combined energy with appropriate weights
        weighted_energy = (
            (0.5 * bass_energy) +      # Bass gets 50% weight
            (0.15 * mid_energy) +       # Mids get 20% weight
            (0.35 * high_energy)        # Highs get 30% weight
        )
        
        # Store each band separately
        with self.lock:
            self.energy_history.append(energy)
            self.bass_history.append(bass_energy)
            
            if not hasattr(self, 'high_history'):
                self.high_history = []
            self.high_history.append(high_energy)
            
            # Keep histories manageable
            if len(self.high_history) > 50:
                self.high_history.pop(0)
        
        # Detect beats with multi-band approach
        if len(self.bass_history) >= 5 and len(self.high_history) >= 5:
            # Bass detection (your existing code)
            bass_short_term = sum(self.bass_history[-5:]) / 5
            bass_long_term = sum(self.bass_history[-20:]) / 20
            bass_beat = (bass_energy > bass_short_term * self.energy_threshold and
                        bass_energy > 0.1)
                        
            # High-frequency detection (for hi-hats, etc)
            high_short_term = sum(self.high_history[-5:]) / 5
            high_long_term = sum(self.high_history[-20:]) / 20
            high_beat = (high_energy > high_short_term * (self.energy_threshold * 1.2) and
                        high_energy > 0.05)
                        
            current_time = time.time()
            
            # Combined beat detection
            if ((bass_beat or high_beat) and 
                current_time - self.last_beat_time > self.min_beat_interval):
                
                self.beat_detected = True
                self.last_beat_time = current_time
                
                # Which type had the stronger relative contribution?
                bass_contrib = bass_energy / (bass_long_term + 0.01)
                high_contrib = high_energy / (high_long_term + 0.01)
                
                # Use whichever is stronger, with appropriate normalization
                if bass_contrib > high_contrib:
                    beat_type = "BASS"
                    energy_val = min(1.0, bass_energy * 2.3)
                else:
                    beat_type = "HIGH"
                    energy_val = min(1.0, high_energy * 2.2)  # Boost high freqs more
                    
                # Add debug info about the beat type
                self.last_beat_type = beat_type
                    
                # Call the callback
                if self.callback_fn:
                    try:
                        self.callback_fn(energy_val)
                    except Exception as e:
                        print(f"Callback error: {e}")
        
        return (None, pyaudio.paContinue)
    
    def stop_listening(self):
        """Stop audio capture and processing"""
        if not self.is_listening:
            return "Not listening"
            
        self.is_listening = False
        
        # Stop and close the stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            
        # Terminate PyAudio
        if self.audio:
            self.audio.terminate()
            self.audio = None
            
        return "Audio processing stopped"
    
    def set_sensitivity(self, value):
        """Set beat detection sensitivity (0.0-1.0)"""
        with self.lock:
            self.sensitivity = max(0.0, min(1.0, value))
            self.energy_threshold = 1.0 + (self.sensitivity * 1.5)  # Map to 1.0-2.5
            return f"Sensitivity set to {self.sensitivity:.2f}"
    
    def get_energy_level(self):
        """Get current audio energy level (0.0-1.0)"""
        with self.lock:
            if not self.is_listening or not self.energy_history:
                return 0.0
            return self.energy_history[-1]

# For testing
if __name__ == "__main__":
    processor = AudioProcessor()
    import serial_handler
    arduino = serial_handler.SerialHandler()
    arduino.connect()
    def on_beat(energy):
        
        # Calculate brightness based on energy
        brightness = min(1.0, energy * 1.8)
        last_brightness = brightness
        
        
        # Visual indicator showing beat type
        beat_type = processor.last_beat_type if hasattr(processor, 'last_beat_type') else "BEAT"
        bar = "█" * int(brightness * 20)
        print(f"{beat_type}! [{bar:<20}] {brightness:.2f}")
        arduino.send_value(brightness)

    
    # Increase sensitivity for better detection
    processor.energy_threshold = 1.5
    processor.set_sensitivity(0.3)  # Higher sensitivity for bass
    processor.start_listening(on_beat)
    print("Listening for beats... Press Ctrl+C to stop")
    
    try:
        # Print current energy levels periodically
        last_print_time = 0
        while True:
            current_time = time.time()
            if current_time - last_print_time > 0.01:
                # Get bass energy from last 5 values in history
                if processor.bass_history:
                    bass = sum(processor.bass_history[-5:]) / 5
                    energy = processor.get_energy_level()
                    threshold = processor.energy_threshold * (sum(processor.bass_history[-10:]) / 10 if processor.bass_history else 0)
                    #print(f"Bass: {bass:.4f} | Energy: {energy:.4f} (threshold: {threshold:.4f})")
                last_print_time = current_time
            time.sleep(0.03)
    except KeyboardInterrupt:
        processor.stop_listening()
        arduino.send_value(0.0)  # Turn off LED
        print("Stopped")