# Hardware:
## Hardware configuration:
### Ambient temperature:

STS35 sensor
Resolution: 0.01 degree
Accuracy: 0.1 degree

 
### Relative humidity:

SHT40 sensor
Resolution: 0.01% RH
Accuracy: +- 1.8RH
       
### Barometric pressure:

BMP390L
Resolution: 0.02hPa
Accuracy: 0.03Pa

### Microcontroller: ESP32 CH340
## Hardware soldering:

ESP32 SDA (pin21) -> all senser SDA in parallel

ESP32 SCL (pin22) -> all senser SCL in parallel

ESP32 3.3v  -> all senser VDD in paralle

ESP32 GND  -> all senser GND in paralle, LED negative pin

ESP32 GPIO 16  -> LED positive pin (with a 220 ohm resistor)

# Software:
## GUI package:

C:\Users\Xia\AppData\Local\Programs\Python\Python39\python.exe -m PyInstaller ^
--onefile ^
--windowed ^
--icon=icon.ico ^
--name=AmbientMonitor ^
E:\Python_GUI\Ambient_monitor\main.py
