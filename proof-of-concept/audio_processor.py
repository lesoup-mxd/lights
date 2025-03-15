import audioop
import threading
import time
import numpy as np
import pyaudio
import math


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
        self.min_beat_interval = 0.007  # Seconds between beats
        self.audio = None
        self.stream = None
        self.callback_fn = None
        self.lock = threading.Lock()
        
        # Smoothing parameters
        self.flux_smoothing_window = 3  # Window size for spectral flux smoothing
        self.energy_smoothing_alpha = 0.7  # EMA coefficient (higher = less smoothing)
        self.smoothed_bass = 0.0
        self.smoothed_flux = 0.0
        self.smoothed_high = 0.0

        self.last_anticipation_time = 0  # Track when we last anticipated a beat
        self.anticipation_lockout = False  # Prevent multiple anticipations of the same beat
        
        # Add rhythm context
        self.rhythm_context = RhythmContext()
        
        # Add groove characteristics
        self.downbeat_detection = True  # Whether to detect bar downbeats
        self.groove_anticipation = True  # Whether to anticipate based on groove
        
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
            frames_per_buffer=2048,  # Increased for better frequency resolution
            stream_callback=self._audio_callback
        )
        print(f"Using device: {self.audio.get_default_input_device_info()['name']}")
        return "Audio processing started (bass-enhanced)"
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        if not self.is_listening:
            return (None, pyaudio.paContinue)
            
        # Convert audio data to numpy array
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        
        # Calculate overall energy (RMS)    
        rms = audioop.rms(in_data, 2)
        energy = min(1.0, rms / 10000.0)
        
        # Perform frequency analysis using FFT
        fft_data = np.abs(np.fft.rfft(audio_data))
        
        # Store previous FFT data for spectral flux calculation
        if not hasattr(self, 'prev_fft_data'):
            self.prev_fft_data = fft_data
            self.spectral_flux_history = []
        
        # Calculate spectral flux (sum of differences between current and previous spectrum)
        # This helps detect onsets better than just energy levels
        flux = np.sum(np.maximum(0, fft_data - self.prev_fft_data))
        normalized_flux = min(1.0, flux / 5000000.0)
        self.prev_fft_data = fft_data.copy()
        
        # Apply window smoothing to spectral flux (NEW)
        if self.flux_smoothing_window > 1:
            # Use a small rolling window average
            if not hasattr(self, 'flux_buffer'):
                self.flux_buffer = np.zeros(self.flux_smoothing_window)
            
            # Roll buffer and add new value
            self.flux_buffer = np.roll(self.flux_buffer, -1)
            self.flux_buffer[-1] = normalized_flux
            
            # Apply Hamming window for better weighting
            window = np.hamming(self.flux_smoothing_window)
            normalized_flux = np.sum(self.flux_buffer * window) / np.sum(window)
        
        # Extract frequency bands (as you already do)
        bass_bins = fft_data[1:7]
        bass_energy = min(1.0, np.sum(bass_bins) / 40000000.0)
        
        mid_bins = fft_data[12:47]
        mid_energy = min(1.0, np.sum(mid_bins) / 100000000.0)
        
        high_bins = fft_data[115:350]
        high_energy = min(1.0, np.sum(high_bins) / 50000000.0)
        
        # Apply exponential moving average smoothing (NEW)
        alpha = self.energy_smoothing_alpha
        self.smoothed_bass = alpha * bass_energy + (1 - alpha) * (self.smoothed_bass if self.smoothed_bass > 0 else bass_energy)
        self.smoothed_flux = alpha * normalized_flux + (1 - alpha) * (self.smoothed_flux if self.smoothed_flux > 0 else normalized_flux)
        self.smoothed_high = alpha * high_energy + (1 - alpha) * (self.smoothed_high if self.smoothed_high > 0 else high_energy)
        
        # Store all relevant history
        with self.lock:
            self.energy_history.append(energy)
            self.bass_history.append(self.smoothed_bass)  # Store smoothed values
            self.spectral_flux_history.append(self.smoothed_flux)
            
            if not hasattr(self, 'high_history'):
                self.high_history = []
            self.high_history.append(self.smoothed_high)
            
            # Keep histories manageable
            if len(self.energy_history) > 50:
                self.energy_history.pop(0)
            if len(self.bass_history) > 50:
                self.bass_history.pop(0)
            if len(self.high_history) > 50:
                self.high_history.pop(0)
            if len(self.spectral_flux_history) > 50:
                self.spectral_flux_history.pop(0)
        
        # Enhanced beat detection with spectral flux
        if len(self.bass_history) >= 5 and len(self.spectral_flux_history) >= 5:
            # Calculate short and long term averages
            flux_short_term = sum(self.spectral_flux_history[-5:]) / 5
            flux_long_term = sum(self.spectral_flux_history[-20:]) / 20 if len(self.spectral_flux_history) >= 20 else flux_short_term
            
            # Bass detection with enhanced sensitivity
            bass_short_term = sum(self.bass_history[-5:]) / 5
            bass_long_term = sum(self.bass_history[-20:]) / 20 if len(self.bass_history) >= 20 else bass_short_term
            
            # High frequency detection
            high_short_term = sum(self.high_history[-5:]) / 5
            high_long_term = sum(self.high_history[-20:]) / 20 if len(self.high_history) >= 20 else high_short_term
            
            # Calculate dynamic thresholds based on recent history
            flux_threshold = flux_long_term * (1.0 - self.sensitivity * 1.5)
            bass_threshold = bass_long_term * self.energy_threshold
            high_threshold = high_long_term * (self.energy_threshold * 1.2)
            
            # Detection conditions
            flux_beat = self.is_true_onset(self.smoothed_flux, self.spectral_flux_history, 1.3) and self.smoothed_flux > flux_threshold
            bass_beat = self.is_true_onset(self.smoothed_bass, self.bass_history, 1.2) and self.smoothed_bass > bass_threshold
            high_beat = self.is_true_onset(self.smoothed_high, self.high_history, 1.4) and self.smoothed_high > high_threshold
            
            current_time = time.time()
            
            # Combined beat detection with spectral flux
            if ((flux_beat or bass_beat or high_beat) and
                current_time - self.last_beat_time > self.min_beat_interval):
                
                self.beat_detected = True
                self.last_beat_time = current_time
                
                # Clear anticipation lockout when a real beat happens
                self.anticipation_lockout = False

                # Add timestamp to beat history for dynamic adjustment
                if not hasattr(self, 'beat_timestamps'):
                    self.beat_timestamps = []
                self.beat_timestamps.append(current_time)
                
                # Determine beat type
                if flux_beat and bass_beat:
                    beat_type = "KICK"  # Strong onset with bass
                    energy_val = min(1.0, (bass_energy * 0.8 + normalized_flux * 0.3))
                elif bass_beat:
                    beat_type = "BASS"
                    energy_val = min(1.0, bass_energy * 1.0)  # No amplification
                elif high_beat:
                    beat_type = "HIGH"
                    energy_val = min(1.0, high_energy * 0.9)
                else:
                    beat_type = "FLUX"  # General onset
                    energy_val = min(1.0, normalized_flux * 0.8)
                    
                # Add debug info about the beat type
                self.last_beat_type = beat_type
                
                # Call the callback
                if self.callback_fn:
                    try:
                        self.callback_fn(energy_val)
                    except Exception as e:
                        print(f"Callback error: {e}")
                
                # After detecting a beat, add to rhythm context
                if hasattr(self, 'rhythm_context'):
                    self.rhythm_context.add_beat(current_time, energy_val, beat_type)
                    
                    # Update current beat position
                    if hasattr(self.rhythm_context, 'beat_positions') and self.rhythm_context.beat_positions:
                        self.current_beat_position = self.rhythm_context.beat_positions[-1][1] - 1  # 0-3 instead of 1-4
    
        # Reset thresholds if no beats for too long
        current_time = time.time()
        if hasattr(self, 'last_beat_time') and current_time - self.last_beat_time > 8.0:
            # Reset to default sensitivity after long silence
            self.energy_threshold = 1.1 - (self.sensitivity * 1.5)
            
            # Also clear beat timestamp history to reset BPM detection
            if hasattr(self, 'beat_timestamps'):
                self.beat_timestamps = []

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
        """Set beat detection sensitivity (0.0-1.0).
        Higher values make detection more sensitive (lower threshold).
        """
        with self.lock:
            self.sensitivity = max(0.0, min(1.0, value))
            # Invert relationship: higher sensitivity = lower threshold
            self.energy_threshold = 2.5 - (self.sensitivity * 1.5)  # Map to 2.5-1.0
            return f"Sensitivity set to {self.sensitivity:.2f}"
    
    def get_energy_level(self):
        """Get current audio energy level (0.0-1.0)"""
        with self.lock:
            if not self.is_listening or not self.energy_history:
                return 0.0
            return self.energy_history[-1]
    
    def is_true_onset(self, current_value, history, threshold_factor=1.2):
        """Determine if a spike is a true onset rather than noise"""
        if len(history) < 5:
            return False
        
        # Get recent values and calculate local stats
        recent = np.array(history[-5:])
        local_mean = np.mean(recent)
        local_std = np.std(recent)
        
        # Calculate rate of change
        if len(history) > 5:
            derivative = current_value - history[-2]
        else:
            derivative = 0
        
        # A true onset has high absolute value, is above local mean,
        # and has a positive derivative
        return (current_value > local_mean + threshold_factor * local_std and 
                derivative > 0 and 
                current_value > 0.08)  # Minimum detection threshold

    def set_smoothing(self, window_size=3, ema_alpha=0.7):
        """Set smoothing parameters

        For different genres the following values can be used:
        Smaller window size (2-3) = faster response, more sensitivity
        Larger window size (5-7) = more stability, less sensitivity
        Higher alpha (0.8-0.9) = more responsive to changes
        Lower alpha (0.3-0.5) = smoother, more stable response
        """
        with self.lock:
            self.flux_smoothing_window = max(1, min(7, window_size))  # Limit window size
            self.energy_smoothing_alpha = max(0.3, min(0.9, ema_alpha))  # Limit alpha range
            return f"Smoothing set to window={self.flux_smoothing_window}, alpha={self.energy_smoothing_alpha:.1f}"

    def adjust_sensitivity_dynamically(self):
        """Dynamically adjust sensitivity based on audio characteristics and BPM"""
        try:
            with self.lock:
                if len(self.bass_history) < 10 or len(self.high_history) < 10:  # REDUCED FROM 20
                    return "Not enough history for dynamic adjustment"
                    
                # Detect BPM first - PASS SAFE_MODE=TRUE TO PREVENT DEADLOCK
                bpm = self.detect_bpm(safe_mode=True)  # THIS IS THE CRITICAL FIX
                
                bpm_text = f", BPM: {bpm:.1f}" if bpm else ""
                
                # Create local copies of data we need outside the lock
                bass_history_copy = self.bass_history[-20:].copy()
                high_history_copy = self.high_history[-20:].copy()
                
                if hasattr(self, 'beat_timestamps'):
                    beat_timestamps_copy = self.beat_timestamps.copy()
                    last_beat_time_copy = self.last_beat_time
                else:
                    beat_timestamps_copy = []
                    last_beat_time_copy = 0
            
            # Release lock before expensive calculations
            
            # 1. Calculate metrics using copied data
            recent_bass = np.array(bass_history_copy)
            recent_high = np.array(high_history_copy)
            bass_mean = np.mean(recent_bass)
            bass_std = np.std(recent_bass)
            high_mean = np.mean(recent_high)
            
            # 2. Calculate beat density (beats per second)
            current_time = time.time()
            recent_beats = [t for t in beat_timestamps_copy if current_time - t < 5.0]
            beat_density = len(recent_beats) / 5.0 if recent_beats else 0
            
            # 3. Determine music characteristics
            bass_to_high_ratio = bass_mean / (high_mean + 0.001)
            variability = bass_std / (bass_mean + 0.001)
            
            # 4. Calculate new sensitivity value
            new_sensitivity = 0.5  # Start with middle value

            # Audio energy adjustments
            if bass_mean < 0.1:
                new_sensitivity -= 0.15  # For quiet audio, lower threshold (was += before)
            elif bass_mean > 0.4:
                new_sensitivity += 0.15  # For loud audio, raise threshold (was -= before)

            # Beat density adjustments
            if beat_density > 2.5:
                new_sensitivity += 0.1  # For rapid beats, be less sensitive (was -= before)
            elif beat_density < 0.5:
                new_sensitivity += 0.1  # More sensitive for sparse beats

            # Variability adjustments 
            if variability < 0.3:
                new_sensitivity -= 0.08  # Less sensitive for steady bass
            elif variability > 0.7:
                new_sensitivity += 0.08  # More sensitive for variable content

            # Time since last beat recovery
            current_time = time.time()
            time_since_beat = current_time - last_beat_time_copy
            if time_since_beat > 3.0:
                recovery_boost = min(0.2, time_since_beat/10)
                new_sensitivity += recovery_boost
                print(f"No beats for {time_since_beat:.1f}s - boosting sensitivity")
            
            # Various adjustments based on audio characteristics...
            # [your existing adjustments here]
            
            # Re-acquire lock for final updates
            with self.lock:
                # Apply limits and smooth changes
                new_sensitivity = max(0.2, min(0.9, new_sensitivity))
                
                # Smooth transition
                self.sensitivity = 0.7 * self.sensitivity + 0.3 * new_sensitivity
                self.energy_threshold = 1.0 + (self.sensitivity * 1.5)
                
                return f"Dynamic sensitivity: {self.sensitivity:.2f}, threshold: {self.energy_threshold:.2f}{bpm_text}"
                
        except Exception as e:
            print(f"Dynamic adjustment error: {str(e)}")
            return f"Error in dynamic adjustment: {str(e)}"

    def detect_bpm(self, safe_mode=False):
        """Detect the BPM of the current audio stream"""
        # Caching - avoid recalculating BPM multiple times in quick succession
        current_time = time.time()
        if hasattr(self, 'last_bpm_calc_time') and current_time - self.last_bpm_calc_time < 0.1:
            if hasattr(self, 'last_bpm_value'):
                return self.last_bpm_value
        
        # Lock handling
        if not safe_mode:
            self.lock.acquire()
        
        try:
            # Check for beat timestamps
            if not hasattr(self, 'beat_timestamps') or len(self.beat_timestamps) < 5:  # Increased min beats
                return None
                
            # Make a copy of timestamps data
            beat_timestamps_copy = self.beat_timestamps.copy()
            
            # Release lock before CPU-intensive calculations
            if not safe_mode:
                self.lock.release()
                
            # Get recent beats only (last 10 seconds)
            recent_beats = [t for t in beat_timestamps_copy if current_time - t < 10.0]
            
            if len(recent_beats) < 5:  # Need more beats for accuracy
                return None
                
            # Sort timestamps and cluster beats that are too close together
            # This prevents multiple detections of same beat from affecting BPM
            sorted_beats = sorted(recent_beats)
            clustered_beats = [sorted_beats[0]]
            
            # Minimum 100ms between separate beats (prevents >600 BPM)
            min_beat_gap = 0.25 # seconds (240 BPM max)
            
            for beat in sorted_beats[1:]:
                if beat - clustered_beats[-1] > min_beat_gap:
                    clustered_beats.append(beat)
            
            if len(clustered_beats) < 4:
                return None
                
            # Calculate intervals between beats
            intervals = np.diff(clustered_beats)
            
            # Filter out extreme intervals:
            # Min: 0.25s = 240 BPM max (was 0.15s = 400 BPM)
            # Max: 1.5s = 40 BPM min (was 2.0s = 30 BPM)
            filtered_intervals = [i for i in intervals if 0.25 < i < 1.5]
            
            if len(filtered_intervals) < 3:
                return None
            
            # Calculate the most common interval range using histogram
            hist, bin_edges = np.histogram(filtered_intervals, bins=8)
            max_bin = np.argmax(hist)
            
            # Get intervals in the most common range
            common_intervals = [i for i in filtered_intervals if 
                                bin_edges[max_bin] <= i <= bin_edges[max_bin+1]]
            
            if not common_intervals:
                common_intervals = filtered_intervals
            
            # Calculate more accurate average interval
            avg_interval = np.mean(common_intervals)
            instantaneous_bpm = 60.0 / avg_interval
            
            # Check for half/double tempo - prefer middle range (80-160 BPM)
            if instantaneous_bpm > 160:
                adjusted_bpm = instantaneous_bpm / 2  # Halve too-fast BPM
            elif instantaneous_bpm < 70:
                adjusted_bpm = instantaneous_bpm * 2  # Double too-slow BPM
            else:
                adjusted_bpm = instantaneous_bpm
                
            # Store in history
            if not hasattr(self, 'bpm_history'):
                self.bpm_history = []
            
            self.bpm_history.append(adjusted_bpm)
            if len(self.bpm_history) > 5:
                self.bpm_history.pop(0)
                
            # Use median for stable BPM
            stable_bpm = np.median(self.bpm_history)
            
            # Save result for caching
            self.last_bpm_calc_time = current_time
            self.last_bpm_value = stable_bpm
            
            return stable_bpm
            
        except Exception as e:
            print(f"BPM detection error: {e}")
            return None
        finally:
            if not safe_mode and self.lock.locked():
                self.lock.release()

    def calculate_next_beat_time(self):
        """Calculate next beat with psychological timing model"""
        if not hasattr(self, 'last_beat_time') or not hasattr(self, 'last_bpm_value'):
            return None
            
        beat_interval = 60.0 / self.last_bpm_value
        
        # Base prediction - mathematical next beat
        next_beat_time = self.last_beat_time + beat_interval
        
        # Apply psychological adjustments if we have rhythm context
        if hasattr(self, 'rhythm_context') and self.rhythm_context.pattern_confidence > 0.4:
            # Adjust based on detected pattern - strong beats come slightly earlier
            if self.rhythm_context.current_pattern:
                # Extract current position in the pattern
                if hasattr(self, 'current_beat_position'):
                    position = (self.current_beat_position + 1) % len(self.rhythm_context.current_pattern)
                    
                    # Apply micro-timing based on position
                    # Downbeats (first beat) often anticipated slightly
                    if position == 0:  # Downbeat
                        next_beat_time -= 0.015  # 15ms early anticipation
                    # Upbeats (beats 2 and 4 in 4/4) slightly delayed
                    elif position in [1, 3]:
                        next_beat_time += 0.010  # 10ms delay
        
        return next_beat_time

class RhythmContext:
    """Analyze and predict rhythmic patterns based on psychological models"""
    def __init__(self):
        self.beat_strengths = []  # Store beat strength history 
        self.beat_positions = []  # Store beat positions in bar (1.0-4.0)
        self.pattern_confidence = 0.0  # Confidence in detected pattern
        self.current_pattern = None
        self.downbeat_energy = 1.0  # Energy multiplier for downbeats
        self.max_pattern_length = 8  # Maximum beats to consider for pattern
        
    def add_beat(self, timestamp, energy, beat_type):
        """Add a beat to the rhythm context"""
        # Calculate position in rhythmic structure (estimate)
        if len(self.beat_strengths) > 0:
            # Estimate beat position based on timing
            last_time = self.beat_positions[-1][0]
            interval = timestamp - last_time
            
            # If interval is close to a reasonable beat duration (0.2-1.0 sec)
            if 0.2 < interval < 1.0:
                # Calculate position within a standard 4/4 bar
                bar_progress = ((interval * 4.0) % 4.0) + 1.0
                position = min(4.0, round(bar_progress))
            else:
                # If interval is unusual, assume it's position 1 (downbeat)
                position = 1.0
        else:
            # First beat is assumed to be beat 1 (downbeat)
            position = 1.0
            
        self.beat_strengths.append((timestamp, energy, beat_type))
        self.beat_positions.append((timestamp, position))
        
        if len(self.beat_strengths) > self.max_pattern_length:
            self.beat_strengths.pop(0)
            self.beat_positions.pop(0)
            
        # Update pattern confidence
        self._detect_pattern()
        
    def _detect_pattern(self):
        """Detect repeating rhythmic patterns"""
        # Need at least 4 beats to detect patterns
        if len(self.beat_strengths) < 4:
            self.pattern_confidence = 0.0
            return
        
        # Get beat types and positions
        types = [b[2] for b in self.beat_strengths]
        positions = [p[1] for p in self.beat_positions]
        energies = [b[1] for b in self.beat_strengths]
        
        # Check for 4-beat pattern
        if len(types) >= 8:
            type_match = sum(1 for i in range(4) if types[i] == types[i+4])
            position_match = sum(1 for i in range(4) if positions[i] == positions[i+4])
            
            # Calculate confidence based on how many elements match
            confidence = (type_match + position_match) / 8.0
            if confidence > 0.6:
                self.pattern_confidence = confidence
                self.current_pattern = types[0:4]
                return
        
        # Check for 2-beat pattern
        if len(types) >= 4:
            type_match = sum(1 for i in range(2) if types[i] == types[i+2])
            position_match = sum(1 for i in range(2) if positions[i] == positions[i+2])
            
            confidence = (type_match + position_match) / 4.0
            if confidence > 0.5:
                self.pattern_confidence = confidence
                self.current_pattern = types[0:2]
                return
        
        # No clear pattern - gradually reduce confidence
        self.pattern_confidence = max(0.0, self.pattern_confidence - 0.1)

# For testing
if __name__ == "__main__":
    processor = AudioProcessor()
    import serial_handler
    arduino = serial_handler.SerialHandler()
    arduino.connect()
    
    def on_beat(energy):
        # Logarithmic mapping
        brightness = 0.8 * (1.0 - math.exp(-2.5 * energy)) / (1.0 - math.exp(-2.5))
        
        # Get BPM once
        bpm = processor.detect_bpm()
        
        # Visual indicator showing beat type
        beat_type = processor.last_beat_type if hasattr(processor, 'last_beat_type') else "BEAT"
        bar = "█" * int(brightness * 20)
        print(f"{beat_type}! [{bar:<20}] {brightness:.2f}" + (f" BPM:{bpm:.1f}" if bpm else ""))
        
        # Send to Arduino
        arduino.send_value_with_bpm(brightness, bpm)
    
    # Increase sensitivity for better detection
    processor.energy_threshold = 1.2
    processor.set_sensitivity(0.5)  # Higher sensitivity for bass
    processor.set_smoothing(window_size=5, ema_alpha=0.8)  # Set smoothing parameters

    processor.start_listening(on_beat)
    print("Listening for beats... Press Ctrl+C to stop")
    
    debug_mode = True # Toggle to see detailed info
    
    try:
        # Print current energy levels periodically
        last_print_time = 0
        last_adjustment_time = 0
        last_debug_time = 0
        
        while True:
            current_time = time.time()
            
            # Print energy levels
            if current_time - last_print_time > 0.1:
                # Get bass energy from last 5 values in history
                if processor.bass_history:
                    bass = sum(processor.bass_history[-5:]) / 5
                    energy = processor.get_energy_level()
                    threshold = processor.energy_threshold * (sum(processor.bass_history[-10:]) / 10 if processor.bass_history else 0)
                last_print_time = current_time
                
            # Periodically adjust sensitivity
            if current_time - last_adjustment_time > 3.0:  # Every 3 seconds seems alr
                result = processor.adjust_sensitivity_dynamically()
                print(f"Dynamic adjustment: {result}")
                
                # Add detailed metrics
                if hasattr(processor, 'bass_history') and processor.bass_history:
                    bass_mean = sum(processor.bass_history[-10:]) / 10
                    variability = np.std(processor.bass_history[-10:]) / (bass_mean + 0.001)
                    print(f"  Metrics: bass_mean={bass_mean:.3f}, variability={variability:.3f}")
                
                last_adjustment_time = current_time
            
            # Anticipate next beat with groove-aware anticipation
            next_beat_time = processor.calculate_next_beat_time()

            if next_beat_time and not processor.anticipation_lockout:
                # Check if we're in the anticipation window (varies by beat importance)
                time_to_beat = next_beat_time - current_time
                
                # Determine anticipation window based on rhythm context
                if hasattr(processor, 'current_beat_position') and processor.current_beat_position == 0:
                    # Downbeat (first beat of bar) - wider anticipation window
                    anticipation_window = 0.15  # 150ms
                    anticipation_brightness = 0.7  # Stronger anticipation
                else:
                    # Regular beat - standard window
                    anticipation_window = 0.1  # 100ms
                    anticipation_brightness = 0.5  # Normal anticipation
                
                # Apply pattern confidence
                if hasattr(processor, 'rhythm_context'):
                    # Higher confidence = earlier anticipation
                    anticipation_window *= (1.0 + processor.rhythm_context.pattern_confidence * 0.5)
                    # Higher confidence = stronger anticipation
                    anticipation_brightness *= (1.0 + processor.rhythm_context.pattern_confidence * 0.2)
                
                if 0 < time_to_beat < anticipation_window:
                    # Calculate anticipation brightness based on distance to beat
                    # Closer to beat = brighter
                    fade_factor = 1.0 - (time_to_beat / anticipation_window)
                    brightness = anticipation_brightness * fade_factor
                    
                    print(f"Groove anticipation: {time_to_beat*1000:.0f}ms to beat, confidence: {processor.rhythm_context.pattern_confidence:.2f}")
                    on_beat(brightness)  # Trigger with calculated brightness
                    
                    # Lock out further anticipations until the next actual beat or timeout
                    processor.anticipation_lockout = True
                    processor.last_anticipation_time = current_time
            
            # Clear anticipation lockout if an actual beat hasn't occurred within 500ms
            if processor.anticipation_lockout and current_time - processor.last_anticipation_time > 0.5:
                processor.anticipation_lockout = False
            
            time.sleep(0.03)
    
    except KeyboardInterrupt:
        arduino.send_value_with_bpm(0, 0)  # Send zero to Arduino on exit
        processor.stop_listening()
        arduino.close()
        print("Stopped")