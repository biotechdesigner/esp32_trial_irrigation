# main.py
import time
import logging
from machine import Pin, I2C, WDT
from secrets import DEVICE_ID, CLOUD_PASSWORD
from arduino_iot_cloud import Task, ArduinoCloudClient, async_wifi_connection

# I2C address of the AM2315
AM2315_I2C_ADDRESS = 0x5C

# Initialize I2C
i2c = I2C(0, scl=Pin(12), sda=Pin(11), freq=10000)
relay = Pin(14, Pin.OUT)

# Global variables for irrigation
irrigation_day = 0
irr_passed = 0
irrigation_interval = 0
intervals_done = 0
relay.value(0)
irrigate = False

# Initialize the watchdog timer with a timeout of 10 seconds
wdt = WDT(timeout=3900000)

def wdt_task(client):
    global wdt
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

def read_irrigate(client, value):
    global irrigate
    irrigate = bool(value)

def on_irrigation_day_changed(client, value):
    global irrigation_day, irr_passed, irrigation_interval, irrigate, intervals_done
    irrigation_day = float(value)
    irrigation_interval = irrigation_day / 14
    print('Updated values from the cloud')
    print('Irrigation of the day: {} min'.format(irrigation_day))
    print("Irrigation interval: {}".format(irrigation_interval))
    irrigate = irrigation_day > 0
    client["irrigate"] = irrigate

def get_intervals_done(client, value):
    global intervals_done
    intervals_done = float(value)
    print('Updated values from the cloud')
    print("Hours of irrigation made: {} hours".format(intervals_done))

def irrigation_task(client):
    global irr_passed, irrigate, irrigation_day, intervals_done
    wdt.feed()
    if irrigation_day > 0:
        relay.value(1)
        print("Relay is ON")
        time.sleep(irrigation_interval * 60)
        relay.value(0)
        print("Relay is OFF")
        
        irr_passed += irrigation_interval
        intervals_done += 1
        print("Amount of irrigations made: {}".format(intervals_done))
        print("Minutes of irrigation made so far: {}".format(irr_passed))
        client["intervals_done"] = intervals_done
        client["irrigate"] = irrigate
        if intervals_done >= 14:
            irrigation_day = 0
            intervals_done = 0
            irr_passed = 0
            irrigate = False
            client["irrigation_day"] = irrigation_day
            client["intervals_done"] = intervals_done
            client["irrigate"] = irrigate
            print("Irrigation of the day completed")
            
        print('Irrigation remaining: {} min'.format(irrigation_day - irr_passed))
    else:
        print('no irrigation this hour')
    wdt.feed()

if __name__ == "__main__":
    logging.basicConfig(
        datefmt="%H:%M:%S",
        format="%(asctime)s.%(msecs)03d %(message)s",
        level=logging.INFO,
    )

    client = ArduinoCloudClient(
        device_id=DEVICE_ID, username=DEVICE_ID, password=CLOUD_PASSWORD
    )
    
    client.register("intervals_done", value=None, on_write=get_intervals_done)
    client.register("irrigation_day", value=None, on_write=on_irrigation_day_changed)
    client.register("irrigate", value=None)
    client.register("humidity", value=None, on_read=read_humidity, interval=900.0)  # 15 minutes
    client.register("temperature", value=None, on_read=read_temperature, interval=900.0)  # 15 minutes
    client.register(Task("irrigation_task", on_run=irrigation_task, interval=3600))  # Run every hour
    client.register(Task("wifi_connection", on_run=async_wifi_connection, interval=60.0))

    client.start()


