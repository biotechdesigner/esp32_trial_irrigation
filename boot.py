import network
import time
import machine
from machine import RTC
import uasyncio as asyncio

from secrets import WIFI_SSID
from secrets import WIFI_PASSWORD
from secrets import DEVICE_ID
from secrets import CLOUD_PASSWORD

# Function to connect to Wi-Fi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    print('Connecting to Wi-Fi...')
    while not wlan.isconnected():
        print('.', end='')
        time.sleep(1)

    print('\nConnected to Wi-Fi')
    print('Network configuration:', wlan.ifconfig())

# Function to get the current time from an NTP server
def set_time():
    import urequests
    try:
        response = urequests.get('http://worldtimeapi.org/api/timezone/Europe/Berlin')
        if response.status_code == 200:
            data = response.json()
            datetime_str = data['datetime']
            year = int(datetime_str[0:4])
            month = int(datetime_str[5:7])
            day = int(datetime_str[8:10])
            hour = int(datetime_str[11:13])
            minute = int(datetime_str[14:16])
            second = int(datetime_str[17:19])
            rtc = RTC()
            rtc.datetime((year, month, day, 0, hour, minute, second, 0))
            print('RTC time set:', rtc.datetime())
        else:
            print('Failed to get current time')
    except Exception as e:
        print('Error fetching time:', e)

# Connect to Wi-Fi and set the RTC time
connect_wifi()
set_time()

# Import and run the scripts
import relay_control
import temp_humidity_server

async def main():
    await asyncio.gather(relay_control.control_relay(), temp_humidity_server.read_sensor_data())

# Start the main function
asyncio.run(main())