import machine
import time
from machine import Pin, I2C, RTC
import urequests
import uos
import uasyncio as asyncio

# I2C address for AM2315
AM2315_I2C_ADDRESS = 0x5C
DATA_FILE = 'temp_humidity_data.csv'  # Changed to relative path

class AM2315:
    def __init__(self, i2c):
        self.i2c = i2c

    def wake_up_sensor(self):
        try:
            self.i2c.writeto(AM2315_I2C_ADDRESS, b'\x00')
            time.sleep(0.1)  # Increased wake-up delay
        except OSError as e:
            print("Failed to wake up the sensor:", e)

    def read_data(self):
        for attempt in range(3):  # Retry up to 3 times
            try:
                self.wake_up_sensor()
                # Send read command
                self.i2c.writeto(AM2315_I2C_ADDRESS, b'\x03\x00\x04')
                time.sleep(0.2)  # Increased read delay
                # Read 8 bytes of data
                data = self.i2c.readfrom(AM2315_I2C_ADDRESS, 8)
                if len(data) == 8:
                    humidity = (data[2] << 8 | data[3]) / 10.0
                    temperature = (data[4] << 8 | data[5]) / 10.0
                    return temperature, humidity
                else:
                    print("Failed to read data from AM2315, attempt", attempt + 1)
                    time.sleep(0.2)  # Short delay before retrying
            except OSError as e:
                if e.args[0] == 19:
                    print('Error reading AM2315: Device not found on attempt', attempt + 1)
                else:
                    print('Error reading AM2315 on attempt {}:'.format(attempt + 1), e)
                time.sleep(0.2)  # Short delay before retrying
        return None, None

def log_data_to_csv(filename, timestamp, temperature, humidity):
    try:
        # Check if the file exists
        file_exists = False
        try:
            with open(filename, 'r'):
                file_exists = True
        except OSError:
            file_exists = False

        # Open file in append mode, create if it does not exist
        with open(filename, 'a') as f:
            if not file_exists:
                f.write('timestamp,temperature,humidity\n')
            f.write('{},{:.1f},{:.1f}\n'.format(timestamp, temperature, humidity))
    except Exception as e:
        print('Error writing to CSV file:', e)

# Function to send data to the server
def send_data_to_endpoint(temperature, humidity):
    try:
        url = 'http://botwifi.nucleo.biobot.farm/sms/+4915205470590/2262533;1:{},2:{}'.format(humidity, temperature)
        response = urequests.post(url)
        print('Data sent:', response.text)
    except Exception as e:
        print('Error sending data to endpoint:', e)
        print('Exception details:', str(e))

# Configuration of the I2C bus
i2c = I2C(0, scl=Pin(12), sda=Pin(11), freq=10000)

# Create AM2315 sensor object
sensor = AM2315(i2c)

# Initialize RTC
rtc = RTC()

# Main loop to read sensor data every 15 minutes and handle logging and sending
async def read_sensor_data():
    while True:
        temperature, humidity = sensor.read_data()
        if temperature is not None and humidity is not None:
            print('Temperature: {:.1f} C'.format(temperature))
            print('Humidity: {:.1f} %'.format(humidity))

            # Get the current timestamp
            datetime = rtc.datetime()
            timestamp = '{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(datetime[0], datetime[1], datetime[2], datetime[4], datetime[5], datetime[6])
            
            # Log data to CSV
            log_data_to_csv(DATA_FILE, timestamp, temperature, humidity)
            
            # Send data to endpoint
            send_data_to_endpoint(temperature, humidity)
        else:
            print("Error reading from AM2315 sensor")

        # Wait for 15 minutes
        await asyncio.sleep(900)