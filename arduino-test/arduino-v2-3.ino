// Protocol Version: 2.3

// LED controller with automatic decay
// Accepts values 0.0-1.0 and handles smooth decay

#define LED_PIN 9 // PWM-capable pin
#define DEBUG 0   // Set to 1 to enable debug, 0 to disable

// Decay parameters
#define DECAY_RATE 0.7  // Decay factor (0.94 = 6% reduction per step)
#define DECAY_DELAY 15  // Milliseconds between decay steps
#define MIN_THRESHOLD 5 // Minimum PWM value before turning off

float currentBrightness = 0.0;   // Current LED brightness (0.0-1.0)
unsigned long lastDecayTime = 0; // Time of last decay

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
    // Read the value (0.0-1.0)
    float value = Serial.parseFloat();

    // If we got a valid value, apply it
    if (value >= 0.0 && value <= 1.0)
    {
      // Set the new brightness value
      currentBrightness = value;

      // Apply gamma correction and update LED immediately
      updateLED();

#if DEBUG
      Serial.print("New brightness: ");
      Serial.println(currentBrightness);
#endif
    }

    // Clear any remaining input
    while (Serial.available() > 0)
    {
      Serial.read();
    }
  }

  // Handle decay in the main loop
  handleDecay();
}

// Apply decay effect over time
void handleDecay()
{
  unsigned long currentTime = millis();

  // Check if it's time to apply decay
  if (currentTime - lastDecayTime >= DECAY_DELAY && currentBrightness > 0)
  {
    lastDecayTime = currentTime;

    // Apply exponential decay
    currentBrightness *= DECAY_RATE;

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