// Resistor Station - Arduino Uno ADC Reader
//
// Circuit:
//   5V pin → R_known (10kΩ, 1%) → A0 → R_unknown → GND
//
// Sends raw ADC ratio (0.0–1.0) as:  A:0.0909\n
// VCC-independent — Pi computes resistance from the ratio directly.

const int ADC_PIN = A0;
const int NUM_SAMPLES = 32;
const int TRIM = 4;
const unsigned long INTERVAL = 50;

int samples[NUM_SAMPLES];

void setup() {
  Serial.begin(115200);
}

void loop() {
  for (int i = 0; i < NUM_SAMPLES; i++) {
    samples[i] = analogRead(ADC_PIN);
  }

  // Sort for trimmed mean
  for (int i = 0; i < NUM_SAMPLES - 1; i++) {
    for (int j = i + 1; j < NUM_SAMPLES; j++) {
      if (samples[j] < samples[i]) {
        int tmp = samples[i];
        samples[i] = samples[j];
        samples[j] = tmp;
      }
    }
  }

  long sum = 0;
  for (int i = TRIM; i < NUM_SAMPLES - TRIM; i++) {
    sum += samples[i];
  }
  float avg = (float)sum / (NUM_SAMPLES - 2 * TRIM);

  // Send ratio (0.0–1.0), NOT voltage
  float ratio = avg / 1023.0;

  Serial.print("A:");
  Serial.println(ratio, 4);

  delay(INTERVAL);
}
