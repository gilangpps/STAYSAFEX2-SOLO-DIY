#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET -1

Adafruit_ADS1115 ads;
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Parameter deteksi
const float THRESHOLD = 0.05; // Volt (sesuaikan berdasarkan noise)
float baseline = 0.0;
unsigned long pulseCount = 0;
float accumulatedDose = 0.0;
const float DOSE_PER_PULSE = 0.001; // μSv/pulse (perlu kalibrasi!)

// Kalibrasi ADC
const float ADC_SCALE = 0.125; // Faktor skala mV per bit (GAIN_TWOTHIRDS)

void setup() {
  Serial.begin(115200);
  
  // Inisialisasi OLED
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED gagal!");
    while(1);
  }
  display.display();
  delay(1000);
  display.clearDisplay();
  
  // Inisialisasi ADS1115
  if (!ads.begin()) {
    Serial.println("ADS1115 gagal!");
    while(1);
  }
  ads.setGain(GAIN_TWOTHIRDS); // ±6.144V range
  calibrateBaseline();
  
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0,0);
  display.println("Sistem Deteksi X-ray");
  display.display();
  delay(2000);
}

void loop() {
  int16_t adcValue = ads.readADC_SingleEnded(0);
  float voltage = adcValue * ADC_SCALE / 1000.0; // Konversi ke Volt
  
  // Deteksi pulsa (peak detection)
  if(voltage > baseline + THRESHOLD) {
    pulseCount++;
    accumulatedDose += DOSE_PER_PULSE;
    
    // Tampilkan pulse info di OLED
    display.clearDisplay();
    display.setCursor(0,0);
    display.print("PULSE: "); display.println(pulseCount);
    display.print("DOSE: "); display.print(accumulatedDose, 3); display.println(" μSv");
    display.print("VOLT: "); display.print(voltage, 3); display.println(" V");
    display.display();
    
    // Kirim data ke serial (format: waktu|tegangan|count|dose)
    Serial.print(millis());
    Serial.print("|");
    Serial.print(voltage, 4);
    Serial.print("|");
    Serial.print(pulseCount);
    Serial.print("|");
    Serial.println(accumulatedDose, 6);
    
    delay(10); // Blocking delay untuk debouncing pulsa
  }
  
  // Update baseline setiap 10 detik
  static unsigned long lastBaselineUpdate = 0;
  if(millis() - lastBaselineUpdate > 10000) {
    calibrateBaseline();
    lastBaselineUpdate = millis();
  }
}

void calibrateBaseline() {
  // Ambil 100 sample untuk kalibrasi baseline
  float sum = 0;
  for(int i = 0; i < 100; i++) {
    sum += ads.readADC_SingleEnded(0) * ADC_SCALE / 1000.0;
    delay(10);
  }
  baseline = sum / 100.0;
  
  // Tampilkan info kalibrasi di OLED
  display.clearDisplay();
  display.setCursor(0,0);
  display.println("KALIBRASI...");
  display.print("BASELINE: ");
  display.print(baseline, 4);
  display.println(" V");
  display.display();
  delay(1000);
}