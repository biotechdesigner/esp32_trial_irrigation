# main.py

import time
import logging
from machine import Pin, I2C
from secrets import DEVICE_ID, CLOUD_PASSWORD
from arduino_iot_cloud import Task, ArduinoCloudClient, async_wifi_connection

AM2315_I2C_ADDRESS = 0x5C

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

i2c = I2C(0, scl=Pin(12), sda=Pin(11), freq=10000)
sensor = AM2315(i2c)
relay = Pin(5, Pin.OUT)

def read_temperature(client):
    temperature, _ = sensor.read_data()
    print('Temperature: {} C'.format(temperature))
    return temperature if temperature is not None else 1000.0

def read_humidity(client):
    _, humidity = sensor.read_data()
    print('Humidity: {} %'.format(humidity))
    return humidity if humidity is not None else 0.0

def on_switch_changed(client, value):
    relay.value(value)
    client["relay"] = value

def fetch_irrigation_minutes(client):
    # Fetch irrigation minutes from cloud (replace with actual fetching logic)
    return 14

def irrigation_task(client):
    irrigation_minutes = fetch_irrigation_minutes(client)
    irrigation_time = irrigation_minutes / 14.0
    for hour in range(14):
        relay.value(1)
        client["relay"] = 1
        time.sleep(irrigation_time * 60)
        relay.value(0)
        client["relay"] = 0
        time.sleep((60 - irrigation_time) * 60)

if __name__ == "__main__":
    logging.basicConfig(
        datefmt="%H:%M:%S",
        format="%(asctime)s.%(msecs)03d %(message)s",
        level=logging.INFO,
    )

    client = ArduinoCloudClient(
        device_id=DEVICE_ID, username=DEVICE_ID, password=CLOUD_PASSWORD
    )

    #client.register("sw1", value=None, on_write=on_switch_changed, interval=0.250)
    #client.register("relay", value=None)
    client.register("humidity", value=None, on_read=read_humidity, interval=60.0)
    time.sleep(10)
    client.register("temperature", value=None, on_read=read_temperature, interval=40.0)
    #client.register(Task("wifi_connection", on_run=async_wifi_connection, interval=60.0))
    #client.register(Task("irrigation_task", on_run=irrigation_task, interval=3600.0))

    client.start()
