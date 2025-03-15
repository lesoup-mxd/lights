// Protocol Version: 3.0 - BPM Required

// LED controller with automatic decay and BPM-aware timing
// Accepts values in format "B:brightness:bpm\n"

#define LED_PIN 9 // PWM-capable pin
#define DEBUG 0   // Set to 1 to enable debug, 0 to disable

// Decay parameters
#define DECAY_DELAY 15  // Milliseconds between decay steps
#define MIN_THRESHOLD 5 // Minimum PWM value before turning off

// Dynamic decay parameters
#define MIN_DECAY_RATE 0.35     // Fast decay (for fast music)
#define MAX_DECAY_RATE 0.94     // Slow decay (for slow music)
#define DEFAULT_DECAY_RATE 0.75 // Default when no BPM is available

float currentBrightness = 0.0;   // Current LED brightness (0.0-1.0)
unsigned long lastDecayTime = 0; // Time of last decay
float decayRate = DEFAULT_DECAY_RATE;
int currentBPM = 120; // Default BPM

void setup()
{
  pinMode(LED_PIN, OUTPUT);
  analogWrite(LED_PIN, 0); // Make sure LED starts off

  // Initialize serial with maximum speed
  Serial.begin(250000);
  Serial.setTimeout(10);
}

void loop()
{
  // Check for new serial data
  if (Serial.available() > 0)
  {
    String rawInput = Serial.readStringUntil('\n');

    // Only support the new format with BPM
    if (rawInput.startsWith("B:"))
    {
      int firstColon = rawInput.indexOf(':');
      int secondColon = rawInput.indexOf(':', firstColon + 1);

      if (firstColon >= 0 && secondColon >= 0)
      {
        // Extract brightness and BPM values
        String brightnessStr = rawInput.substring(firstColon + 1, secondColon);
        String bpmStr = rawInput.substring(secondColon + 1);

        float value = brightnessStr.toFloat();
        int bpm = bpmStr.toInt();

        // Validate values
        if (value >= 0.0 && value <= 1.0 && bpm > 0)
        {
          currentBPM = bpm;
          currentBrightness = value;

          // Calculate appropriate decay rate based on BPM
          // Faster music (higher BPM) = faster decay
          if (bpm > 0)
          {
            // Map BPM range (60-180) to decay range (MAX_DECAY_RATE to MIN_DECAY_RATE)
            // Constrain BPM to avoid extreme values
            int constrainedBPM = constrain(bpm, 60, 180);
            decayRate = map(constrainedBPM, 60, 180, MAX_DECAY_RATE * 100, MIN_DECAY_RATE * 100) / 100.0;
          }

          updateLED();

#if DEBUG
          Serial.print("New brightness: ");
          Serial.print(currentBrightness);
          Serial.print(", BPM: ");
          Serial.print(currentBPM);
          Serial.print(", Decay Rate: ");
          Serial.println(decayRate, 3);
#endif
        }
      }
    }

    // Clear any remaining input
    while (Serial.available() > 0)
    {
      Serial.read();
    }
  }

  // Apply decay with the dynamically calculated rate
  handleDecay();
}

// Apply decay effect with dynamic decay rate
void handleDecay()
{
  unsigned long currentTime = millis();

  // Check if it's time to apply decay
  if (currentTime - lastDecayTime >= DECAY_DELAY && currentBrightness > 0)
  {
    lastDecayTime = currentTime;

    // Apply exponential decay with dynamically set rate
    currentBrightness *= decayRate;

    // If brightness is very low, turn off completely
    if (currentBrightness * 255 < MIN_THRESHOLD)
    {
      currentBrightness = 0;
    }

    // Update the LED with the new value
    updateLED();

#if DEBUG
    if (currentBrightness > 0)
    {
      Serial.print("Decay: ");
      Serial.println(currentBrightness);
    }
#endif
  }
}

// Apply gamma correction and update the LED
void updateLED()
{
  // Apply gamma correction for more natural brightness perception
  float gamma = 2.8;
  float correctedBrightness = pow(currentBrightness, 1.0 / gamma);

  // Convert to PWM range (0-255)
  int pwmValue = int(correctedBrightness * 255.0);
  analogWrite(LED_PIN, pwmValue);
}