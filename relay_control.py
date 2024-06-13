import machine
import time
from machine import Pin, RTC
import uasyncio as asyncio

# Configuration of the relay
relay_pin = Pin(14, Pin.OUT)
relay_pin.off()

# Initialize RTC
rtc = RTC()

# File to save relay state times
DATA_FILE = 'relay_log.csv'

def log_relay_state(state, remaining_minutes=None):
    try:
        # Check if the file exists
        file_exists = False
        try:
            with open(DATA_FILE, 'r'):
                file_exists = True
        except OSError:
            file_exists = False

        # Open file in append mode, create if it does not exist
        with open(DATA_FILE, 'a') as f:
            if not file_exists:
                f.write('timestamp,state,remaining_minutes\n')
            datetime = rtc.datetime()
            timestamp = '{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(datetime[0], datetime[1], datetime[2], datetime[4], datetime[5], datetime[6])
            if remaining_minutes is not None:
                f.write('{}, {}, {}\n'.format(timestamp, state, remaining_minutes))
            else:
                f.write('{}, {}\n'.format(timestamp, state))
    except Exception as e:
        print('Error writing to CSV file:', e)

# Function to get the watering duration for the day (fixed value for testing)
def get_watering_duration():
    duration = 2.3  # Fixed watering duration of 2.3 minutes for testing
    print('Got watering duration:', duration, 'minutes')
    return duration

# Uncomment and use this function to fetch watering duration from an endpoint
# def get_watering_duration_from_endpoint():
#     try:
#         response = urequests.get(watering_duration_endpoint)
#         if response.status_code == 200:
#             watering_duration = response.json()['watering_duration']
#             print('Got watering duration:', watering_duration, 'minutes')
#             return watering_duration
#         else:
#             print('Failed to get watering duration')
#             return 0
#     except Exception as e:
#         print('Error fetching watering duration:', e)
#         return 0

# Main loop to control the relay
async def control_relay():
    watering_duration = 0
    should_water = False
    intervals = 14  # Number of watering intervals from 7am to 9pm

    while True:
        datetime = rtc.datetime()
        current_hour = datetime[4]
        current_minute = datetime[5]

        # At 7:00am, get the total watering time for the day
        if current_hour == 7 and current_minute == 0:
            watering_duration = get_watering_duration()
            if watering_duration > 0:
                should_water = True
                # Calculate the watering duration for each interval
                watering_duration = watering_duration / intervals

        # Control watering every hour from 7am to 9pm
        print (watering_duration)
        if should_water and 7 <= current_hour < 21 and current_minute == 35:
            remaining_time = watering_duration * (intervals - ((current_hour - 7) + 1))
            log_relay_state('START', remaining_time)
            relay_pin.on()  # Activate the relay (turn on the pumps)
            print('Remaining irrigation time for today: {:.1f} minutes'.format(remaining_time))
            await asyncio.sleep(watering_duration * 60)  # Water for the calculated duration
            relay_pin.off()  # Deactivate the relay (turn off the pumps)
            remaining_time -= watering_duration
            log_relay_state('STOP', remaining_time)
            print('Remaining irrigation time for today: {:.1f} minutes'.format(remaining_time))
            await asyncio.sleep(60)  # Wait for 1 minute to avoid multiple triggers within the same minute

        # Sleep for a minute to avoid checking every second
        await asyncio.sleep(60)

# Start controlling the relay
control_relay()