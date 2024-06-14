# main.py

import time
import logging
from machine import Pin, I2C
from secrets import DEVICE_ID, CLOUD_PASSWORD
from arduino_iot_cloud import Task, ArduinoCloudClient, async_wifi_connection

# I2C address of the AM2315
AM2315_I2C_ADDRESS = 0x5C

# Initialize I2C
i2c = I2C(0, scl=Pin(12), sda=Pin(11), freq=10000)
relay = Pin(14, Pin.OUT)

def wdt_task(client):
    global wdt
    # Update the WDT to prevent it from resetting the system
    wdt.feed()

def wake_up_sensor():
    try:
        i2c.writeto(AM2315_I2C_ADDRESS, b'\x00')
        time.sleep(0.1)
    except OSError:
        pass

def read_data():
    for attempt in range(3):  # Retry up to 3 times
        try:
            wake_up_sensor()
            # Send read command
            i2c.writeto(AM2315_I2C_ADDRESS, b'\x03\x00\x04')
            time.sleep(0.2)  # Increased read delay
            # Read 8 bytes of data
            data = i2c.readfrom(AM2315_I2C_ADDRESS, 8)
            if len(data) == 8 and data[0] == 0x03 and data[1] == 0x04:
                humidity = (data[2] << 8 | data[3]) / 10.0
                temperature = (data[4] << 8 | data[5]) / 10.0
                return temperature, humidity
            else:
                print(f"Invalid data received, attempt {attempt + 1}")
        except OSError as e:
            print(f"Error reading AM2315 on attempt {attempt + 1}: {e}")
        time.sleep(0.5 * (attempt + 1))  # Exponential back-off
    return None, None

def read_temperature(client):
    temperature, _ = read_data()
    print('Temperature: {} C'.format(temperature))
    return temperature if temperature is not None else 1000.0

def read_humidity(client):
    _, humidity = read_data()
    print('Humidity: {} %'.format(humidity))
    return humidity if humidity is not None else -1000.0

def on_relay_changed(client, value):
    relay.value(value)
    client["relay"] = bool(value)
    print(f"Relay state changed to: {bool(value)}")

def fetch_irrigation_minutes(client):
    # Fetch irrigation minutes from cloud (replace with actual fetching logic)
    return 14

def irrigation_task(client):
    print("Irrigation task started")
    relay.value(1)  # Turn on the relay
    client["relay"] = True  # Update the cloud variable as boolean
    print("Relay is ON and updated to cloud")
    time.sleep(30)  # Wait for 30 seconds
    relay.value(0)  # Turn off the relay
    client["relay"] = False  # Update the cloud variable as boolean
    print("Relay is OFF and updated to cloud")
    # irrigation_minutes = fetch_irrigation_minutes(client)
    # irrigation_time = irrigation_minutes / 14.0
    # for hour in range(14):
    #     relay.value(1)
    #     client["relay"] = 1
    #     time.sleep(irrigation_time * 60)
    #     relay.value(0)
    #     client["relay"] = 0
    #     time.sleep((60 - irrigation_time) * 60)

if __name__ == "__main__":
    logging.basicConfig(
        datefmt="%H:%M:%S",
        format="%(asctime)s.%(msecs)03d %(message)s",
        level=logging.INFO,
    )

    client = ArduinoCloudClient(
        device_id=DEVICE_ID, username=DEVICE_ID, password=CLOUD_PASSWORD
    )
    
    client.register("relay", value=None, on_write=on_relay_changed)
    client.register("humidity", value=None, on_read=read_humidity, interval=60.0)
    client.register("temperature", value=None, on_read=read_temperature, interval=55.0)

    if False:
        try:
            from machine import WDT
            # Enable the WDT with a timeout of 5s (1s is the minimum)
            wdt = WDT(timeout=7500)
            client.register(Task("watchdog_task", on_run=wdt_task, interval=1.0))
        except (ImportError, AttributeError):
            pass
          
    client.start()
