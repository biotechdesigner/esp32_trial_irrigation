# main.py
import time
from time import sleep_ms
import logging
import ntptime
import utime
from machine import Pin, I2C, WDT
from secrets import DEVICE_ID, CLOUD_PASSWORD, WIFI_PASS, WIFI_SSID
import network
from arduino_iot_cloud import Task, ArduinoCloudClient, async_wifi_connection

# I2C address of the AM2315
AM2315_I2C_ADDRESS = 0x5C

# Initialize I2C
i2c = I2C(0, scl=Pin(4), sda=Pin(3), freq=10000)
relay = Pin(14, Pin.OUT)

# Global variables for irrigation
irrigation_day = 0
irr_passed = 0
irrigation_interval = 0
intervals_done = 0
relay.value(0)
irrigate = False

is_connected_to_wifi = False
is_connected_to_cloud = False

# Initialize the watchdog timer with a timeout of 10 seconds
wdt = WDT(timeout=3900000)

def wdt_task(client):
    global wdt
    wdt.feed()

def sync_ntp():
    try:
        ntptime.settime()
        print("Hora sincronizada con NTP")
    except:
        print("Error al sincronizar la hora")

def get_time():
    return time.localtime()

def print_time():
    try:
        ntptime.settime()
        print("Hora sincronizada con NTP")
    except:
        print("Error al sincronizar la hora")
    current_time = get_time()
    formatted_time = "{0}/{1}/{2} {3}:{4}:{5}".format(
        current_time[0], current_time[1], current_time[2],
        current_time[3], current_time[4], current_time[5]
    )
    return formatted_time

def setup():
    logging.basicConfig(
        datefmt="%H:%M:%S",
        format="%(asctime)s %(message)s",
        level=logging.DEBUG,
    )
    logging.info("end of setup")
    
def check_connection(client): 
  global is_connected_to_cloud
  if not is_connected_to_cloud:
    thing_id = client.thing_id
    logging.info(f"******* CLIENT: {client.thing_id}")
    if thing_id is not None:
      logging.info(f"******* Thing ID: {thing_id}")
      is_connected_to_cloud = True

def wifi_connect():
    global is_connected_to_wifi
    if not WIFI_SSID or not WIFI_PASS:
        raise (Exception("Network is not configured. Set SSID and passwords in secrets.py"))
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    while not wlan.isconnected():
        logging.info("Trying to connect. Note this may take a while...")
        sleep_ms(500)
    logging.info(f"WiFi Connected {wlan.ifconfig()}")
    is_connected_to_wifi = True
    print(print_time())
    
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
                logging.warning(f"Invalid data received, attempt {attempt + 1}")
        except OSError as e:
            logging.error(f"Error reading AM2315 on attempt {attempt + 1}: {e}")
        time.sleep(0.5 * (attempt + 1))  # Exponential back-off
    return None, None

def loop(client):  
    global is_connected_to_cloud
    logging.info(f"*** In loop, is connected? {is_connected_to_cloud}")
    if is_connected_to_cloud:
        temperature, humidity = read_data()
        if temperature is not None and humidity is not None:
            logging.info(f'Temperature: {temperature} C')
            logging.info(f'Humidity: {humidity} %')
            client["humidity"] = humidity
            client["temperature"] = temperature
        else:
            logging.error("Failed to read sensor data")
    else:
        logging.warning("Not connected to cloud, skipping sensor read")

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
    #If there is irrigation then it will turn the water pumps on
    if irrigation_day > 0:
        relay.value(1)
        print("Relay is ON")
        time.sleep(irrigation_interval * 60)
        relay.value(0)
        print("Relay is OFF")
        #After irrigation it will register the irrigation and update the variables to the cloud
        irr_passed += irrigation_interval
        intervals_done += 1
        print("Amount of irrigations made: {}".format(intervals_done))
        print("Minutes of irrigation made so far: {}".format(irr_passed))
        client["intervals_done"] = intervals_done
        client["irrigate"] = irrigate
        #After 14 irrigations it will set up everything to 0 to start again when irrigation is set again in Arduino Cloud
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

def arduino_client_start():
    client = ArduinoCloudClient(
        device_id=DEVICE_ID, username=DEVICE_ID, password=CLOUD_PASSWORD
    )
    
    client.register("intervals_done", value=None, on_write=get_intervals_done)
    client.register("irrigation_day", value=None, on_write=on_irrigation_day_changed)
    client.register("irrigate", value=None)
    client.register("humidity", value=None)
    client.register("temperature", value=None)
    client.register(Task("irrigation_task", on_run=irrigation_task, interval=3600.0))  # Run every hour
    client.register(Task("loop", on_run=loop, interval=60.0))
    client.register(Task("check_connection", on_run=check_connection, interval=1.0))
    client.start()

if __name__ == "__main__":
    setup()
    wifi_connect()
    arduino_client_start()

    


