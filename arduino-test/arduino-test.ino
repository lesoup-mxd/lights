void setup() {
  Serial.begin(9600);
  delay(1000);
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command == "PING") {
      Serial.println("PONG");
    } 
    else if (command == "LED_ON") {
      digitalWrite(8, HIGH);
      Serial.println("LED turned ON");
    } 
    else if (command == "LED_OFF") {
      digitalWrite(8, LOW);
      Serial.println("LED turned OFF");
    } 
    else if (command == "STATUS") {
      Serial.println("Arduino is running. Uptime: " + String(millis()/1000) + "s");
    } 
    else {
      Serial.println("Unknown command: " + command);
    }
  }
}