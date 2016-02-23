import argparse
from time import sleep
from datetime import datetime

import paho.mqtt.client as mqtt
import RPi.GPIO as gpio


PIN = 14
TOPIC = "home/power/meter"
RECONNECT_DELAY_SECS = 2
DEFAULT_MQTT_PORT = 1883
FLASH_SECS = 0.02
FLASH_TOLERANCE_PCT = 10


def on_connect(client, userdata, flags, rc):
    print "Connected with result code " + str(rc)


def on_disconnect(client, userdata, rc):
    print "Disconnected from MQTT server with code: %s" % rc
    while rc != 0:
        sleep(RECONNECT_DELAY_SECS)
        print "Reconnecting to MQTT server..."
        rc = client.reconnect()


def publish_power(watts):
    watts = round(watts, 2)
    client.publish(TOPIC, payload=watts)
    print "Published value of %s Watts." % watts


def within_tolerance(val, nominal, tolerance_percent):
    tol = tolerance_percent/100.0
    return nominal*(1-tol) <= val <= nominal*(1+tol)


def handle_change(val, last_val, on_dt, off_dt):
    print "Value changed to %r" % val
    now = datetime.now()

    if val == 1:
        return now, off_dt

    if off_dt is None:
        return on_dt, now

    if on_dt is None:
        return on_dt, off_dt

    on_secs = (now - on_dt).total_seconds()
    if not within_tolerance(on_secs, FLASH_SECS, FLASH_TOLERANCE_PCT):
        print "Detected flash duration was outside tolerance: %s" % on_secs
        return None, None

    secs_since_last_off = (now - off_dt).total_seconds()
    print "Time since last flash: %r" % secs_since_last_off
    publish_power(3600.0 / secs_since_last_off)
    return on_dt, now


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("user")
    p.add_argument("password")
    p.add_argument("host")
    p.add_argument("--port", type=int, default=DEFAULT_MQTT_PORT)
    args = p.parse_args()

    client = mqtt.Client(client_id="power", clean_session=False)
    client.on_connect = on_connect
    client.username_pw_set(args.user, args.password)
    client.connect(args.host, args.port, 60)
    client.loop_start()

    gpio.setwarnings(False)
    gpio.setmode(gpio.BCM)
    gpio.setup(PIN, gpio.IN)

    last_val = 0
    on_dt = None
    off_dt = None
    try:
        while True:
            sleep(0.0025)
            val = gpio.input(PIN)
            if val != last_val:
                on_dt, off_dt = handle_change(val, last_val, on_dt, off_dt)
            last_val = val
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
