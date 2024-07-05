# boot.py
import network
import time
import machine
from secrets import WIFI_SSID, WIFI_PASS

def connect_to_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)

    max_attempts = 10
    attempt = 0
    while not wlan.isconnected() and attempt < max_attempts:
        print('Attempting to connect to WiFi...')
        attempt += 1
        time.sleep(1)

    if wlan.isconnected():
        print('Connected to WiFi:', wlan.ifconfig())
    else:
        print('Failed to connect to WiFi')
        time.sleep(5)  # Wait a bit before resetting
        machine.reset()  # Reset the device if it fails to connect

try:
    connect_to_wifi()
except Exception as e:
    print('An error occurred:', e)
    time.sleep(5)
    machine.reset()

# After connecting to Wi-Fi, start the main script
try:
    import main
except Exception as e:
    print('An error occurred in main:', e)
    time.sleep(5)
    machine.reset()
