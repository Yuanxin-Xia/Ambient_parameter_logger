#include <Wire.h>
#include "DFRobot_SHT40.h"
#include "DFRobot_STS3X.h"
#include <DFRobot_BMP3XX.h>
#include "BluetoothSerial.h"

// ========== Bluetooth Serial ==========
BluetoothSerial SerialBT;

// ========== I2C Addresses and Sensor Objects (adjust if needed) ==========
#define SHT40_I2C_ADDRESS SHT40_AD1B_IIC_ADDR
DFRobot_SHT40 sht40(SHT40_I2C_ADDRESS);

#define STS35_I2C_ADDRESS STS3X_I2C_ADDRESS_B
DFRobot_STS3X sts35(&Wire, STS35_I2C_ADDRESS);

DFRobot_BMP390L_I2C bmp390l(&Wire, bmp390l.eSDOVDD);

// LED pin
const int ledPin = 16;

// Global interval in milliseconds (default 5000 = 5s)
unsigned long readingInterval = 5000;  

// This function checks for incoming commands on a given Stream (Serial or SerialBT)
void handleSerialCommands(Stream &inStream) {
  while (inStream.available() > 0) {
    String line = inStream.readStringUntil('\n');
    line.trim();
    // Example command: "GAP,5000"
    if (line.startsWith("GAP,")) {
      String numStr = line.substring(4);  // everything after "GAP,"
      unsigned long newInterval = numStr.toInt();
      if (newInterval > 0) {
        readingInterval = newInterval;
        // optional: clamp to a minimum to avoid negative or zero delays
        if (readingInterval < 100) {
          readingInterval = 100;
        }
        inStream.println("Interval updated to: " + String(readingInterval) + " ms");
      } else {
        inStream.println("Invalid interval: " + numStr);
      }
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(ledPin, OUTPUT);
  // Wait for Serial (optional)
  while (!Serial) { ; }

  Serial.println("Initializing...");

  // ========== I2C init ==========
  Wire.begin();

  // ========== SHT40 init ==========
  sht40.begin();
  uint32_t sht40_id = sht40.getDeviceID();
  while (sht40_id == 0) {
    Serial.println("SHT40 ID retrieval error! Check connections.");
    delay(1000);
    sht40_id = sht40.getDeviceID();
  }
  Serial.print("SHT40 ID: 0x");
  Serial.println(sht40_id, HEX);

  // ========== STS35 init ==========
  while (!sts35.begin()) {
    Serial.println("Failed to initialize STS35!");
    delay(1000);
  }
  sts35.setFreq(sts35.e10Hz);
  Serial.println("STS35 ready.");

  // ========== BMP390L init ==========
  int bmp_result;
  while ((bmp_result = bmp390l.begin()) != ERR_OK) {
    if (bmp_result == ERR_DATA_BUS) {
      Serial.println("BMP390L Data Bus Error!");
    } else if (bmp_result == ERR_IC_VERSION) {
      Serial.println("BMP390L Chip Version Mismatch!");
    } else {
      Serial.println("BMP390L Init Failed!");
    }
    delay(3000);
  }
  bmp390l.setSamplingMode(DFRobot_BMP390L_I2C::eUltraPrecision);
  Serial.println("BMP390L ready.");

  // ========== Bluetooth init ==========
  if (!SerialBT.begin("ESP32_Sensor")) {
    Serial.println("Bluetooth init error!");
  } else {
    Serial.println("Bluetooth started. Name: ESP32_Sensor");
  }

  Serial.println("Setup complete.");
}

void loop() {
  // Check if there's any command from Hardware Serial or Bluetooth
  handleSerialCommands(Serial);
  handleSerialCommands(SerialBT);

  // Read sensors
  float humidity = sht40.getHumidity(PRECISION_HIGH);
  float temperature_sts35 = sts35.getTemperaturePeriodC();
  float pressure_bmp390l = bmp390l.readPressPa();

  // If all are valid, output CSV line: "DATA,<temp>,<humi>,<press>"
  if (humidity != MODE_ERR &&
      temperature_sts35 != MODE_ERR &&
      pressure_bmp390l != MODE_ERR) {
    // Optional: heater if humidity > 80%
    if (humidity > 80.0) {
      sht40.enHeater(POWER_CONSUMPTION_H_HEATER_1S);
    }
    // Output single line to both Serial and Bluetooth
    Serial.printf("DATA,%.2f,%.2f,%.2f\n", 
                  temperature_sts35, humidity, pressure_bmp390l);
    SerialBT.printf("DATA,%.2f,%.2f,%.2f\n", 
                    temperature_sts35, humidity, pressure_bmp390l);
  } else {
    // Error reading
    Serial.println("DATA,ERROR");
    SerialBT.println("DATA,ERROR");
  }

  // Blink LED quickly, just to indicate we took a reading
  digitalWrite(ledPin, HIGH);
  delay(200);
  digitalWrite(ledPin, LOW);

  // Now wait the remainder of readingInterval
  // (If readingInterval < 200, you might adjust to avoid negative delays)
  if (readingInterval > 200) {
    delay(readingInterval - 200);
  } else {
    delay(0);
  }
}
