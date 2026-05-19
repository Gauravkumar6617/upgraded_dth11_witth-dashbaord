
import machine
import dht
import time
import urequests
import network
import ujson

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────
WIFI_SSID         = "Galaxy Tab A9 2252"
WIFI_PASSWORD     = "12345678"
SUPABASE_URL      = ""
SUPABASE_KEY      = ""
DHT_PIN           = 4       # GPIO pin connected to DHT11 data pin
READING_INTERVAL  = 60      # seconds between readings
SENSOR_RETRIES    = 3       # how many times to retry a bad sensor read
WIFI_TIMEOUT      = 20      # seconds before WiFi gives up
SENSOR_WARMUP     = 2       # seconds to let DHT11 stabilise after boot

# ─────────────────────────────────────────
#  LOGGING HELPERS
# ─────────────────────────────────────────
# Log levels
DEBUG = 0
INFO  = 1
WARN  = 2
ERROR = 3

LOG_LEVEL = INFO            # change to DEBUG for verbose output
_LEVEL_NAMES = {DEBUG: "DEBUG", INFO: "INFO ", WARN: "WARN ", ERROR: "ERROR"}

_reading_count  = 0         # total readings attempted
_success_count  = 0         # readings successfully sent to Supabase
_fail_count     = 0         # failed readings / send errors


def _timestamp():
    """Return a simple uptime string mm:ss (no RTC needed)."""
    t = time.ticks_ms() // 1000
    return "[{:02d}:{:02d}]".format(t // 60, t % 60)


def log(level, message):
    """Print a timestamped log line if level >= LOG_LEVEL."""
    if level >= LOG_LEVEL:
        print("{} {} {}".format(_timestamp(), _LEVEL_NAMES.get(level, "?????"), message))


def log_separator(char="─", width=50):
    print(char * width)


def log_stats():
    """Print a running summary of read/send statistics."""
    log_separator()
    log(INFO, "─── SESSION STATS ─────────────────────────────")
    log(INFO, "  Readings attempted : {}".format(_reading_count))
    log(INFO, "  Successfully sent  : {}".format(_success_count))
    log(INFO, "  Failed             : {}".format(_fail_count))
    success_rate = (_success_count / _reading_count * 100) if _reading_count else 0
    log(INFO, "  Success rate       : {:.1f}%".format(success_rate))
    log_separator()


# ─────────────────────────────────────────
#  SENSOR INITIALISATION
# ─────────────────────────────────────────
log(DEBUG, "Initialising DHT11 on GPIO{}".format(DHT_PIN))
sensor = dht.DHT11(machine.Pin(DHT_PIN))


# ─────────────────────────────────────────
#  WIFI
# ─────────────────────────────────────────
def connect_wifi():
    """Connect to WiFi. Returns True on success."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        log(INFO, "WiFi already connected. IP: {}".format(wlan.ifconfig()[0]))
        return True

    log(INFO, "Connecting to WiFi SSID: '{}'".format(WIFI_SSID))
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    elapsed = 0
    while not wlan.isconnected() and elapsed < WIFI_TIMEOUT:
        time.sleep(1)
        elapsed += 1
        log(DEBUG, "  ... waiting {}s / {}s".format(elapsed, WIFI_TIMEOUT))

    if wlan.isconnected():
        cfg = wlan.ifconfig()
        log(INFO, "WiFi connected!")
        log(INFO, "  IP      : {}".format(cfg[0]))
        log(INFO, "  Subnet  : {}".format(cfg[1]))
        log(INFO, "  Gateway : {}".format(cfg[2]))
        log(INFO, "  DNS     : {}".format(cfg[3]))
        return True
    else:
        log(ERROR, "WiFi connection FAILED after {}s".format(WIFI_TIMEOUT))
        return False


# ─────────────────────────────────────────
#  SENSOR
# ─────────────────────────────────────────
# Valid DHT11 output ranges
TEMP_MIN, TEMP_MAX    = 0,  50   # °C
HUMID_MIN, HUMID_MAX  = 20, 90   # %RH


def read_sensor():
    """
    Read temperature and humidity with retries and sanity checks.
    Returns (temp, humidity) or (None, None) on failure.
    """
    global _reading_count
    _reading_count += 1

    log(DEBUG, "Sensor read attempt (reading #{})".format(_reading_count))

    for attempt in range(1, SENSOR_RETRIES + 1):
        try:
            time.sleep_ms(500)       # settle between attempts
            sensor.measure()
            time.sleep_ms(100)       # allow measurement to complete
            temp     = sensor.temperature()
            humidity = sensor.humidity()

            # Sanity check – DHT11 occasionally returns 0/0 or garbage
            if not (TEMP_MIN <= temp <= TEMP_MAX):
                log(WARN, "Attempt {}/{}: temperature out of range: {}°C".format(
                    attempt, SENSOR_RETRIES, temp))
                continue

            if not (HUMID_MIN <= humidity <= HUMID_MAX):
                log(WARN, "Attempt {}/{}: humidity out of range: {}%".format(
                    attempt, SENSOR_RETRIES, humidity))
                continue

            log(INFO, "Sensor OK  →  Temperature: {}°C  |  Humidity: {}%".format(
                temp, humidity))
            return temp, humidity

        except OSError as e:
            log(WARN, "Attempt {}/{}: OSError reading sensor: {}".format(
                attempt, SENSOR_RETRIES, e))
            log(DEBUG, "  Tip: check pull-up resistor (4.7k–10kΩ) on DATA line")
            time.sleep(1)

        except Exception as e:
            log(ERROR, "Attempt {}/{}: unexpected sensor error: {}".format(
                attempt, SENSOR_RETRIES, e))
            time.sleep(1)

    log(ERROR, "All {} sensor read attempts failed for reading #{}".format(
        SENSOR_RETRIES, _reading_count))
    return None, None


# ─────────────────────────────────────────
#  SUPABASE
# ─────────────────────────────────────────
def send_to_supabase(temperature, humidity):
    """
    POST sensor data to Supabase.
    Returns True on success, False on failure.
    """
    global _success_count, _fail_count

    url = "{}/rest/v1/sensor_data".format(SUPABASE_URL)
    headers = {
        "apikey"       : SUPABASE_KEY,
        "Authorization": "Bearer {}".format(SUPABASE_KEY),
        "Content-Type" : "application/json",
        "Prefer"       : "return=minimal"
    }
    payload = {"temperature": temperature, "humidity": humidity}

    log(DEBUG, "POST {}".format(url))
    log(DEBUG, "  Payload: {}".format(ujson.dumps(payload)))

    try:
        response = urequests.post(url, data=ujson.dumps(payload), headers=headers)
        status   = response.status_code
        response.close()

        if status == 201:
            _success_count += 1
            log(INFO, "Supabase OK (HTTP 201)  →  total sent: {}".format(_success_count))
            return True
        else:
            _fail_count += 1
            log(ERROR, "Supabase error HTTP {}  →  total failed: {}".format(
                status, _fail_count))
            return False

    except OSError as e:
        _fail_count += 1
        log(ERROR, "Network error sending to Supabase: {}".format(e))
        log(DEBUG, "  Check WiFi is still connected")
        return False

    except Exception as e:
        _fail_count += 1
        log(ERROR, "Unexpected error sending to Supabase: {}".format(e))
        return False


# ─────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────
def main():
    log_separator("═")
    log(INFO, "  ESP32 DHT11 → Supabase Logger  ")
    log_separator("═")
    log(INFO, "  DHT_PIN          : GPIO{}".format(DHT_PIN))
    log(INFO, "  READING_INTERVAL : {}s".format(READING_INTERVAL))
    log(INFO, "  SENSOR_RETRIES   : {}".format(SENSOR_RETRIES))
    log(INFO, "  LOG_LEVEL        : {}".format(_LEVEL_NAMES.get(LOG_LEVEL)))
    log_separator("═")

    # ── WiFi ──────────────────────────────
    if not connect_wifi():
        log(ERROR, "Cannot proceed without WiFi. Restarting in 5s...")
        time.sleep(5)
        machine.reset()

    # ── DHT11 warm-up ─────────────────────
    log(INFO, "Waiting {}s for DHT11 to stabilise...".format(SENSOR_WARMUP))
    time.sleep(SENSOR_WARMUP)
    log(INFO, "Ready. Starting read loop (Ctrl-C to stop)")
    log_separator()

    loop_count = 0

    while True:
        try:
            loop_count += 1
            log(INFO, "── Loop #{} ──".format(loop_count))

            # Read sensor
            temp, humidity = read_sensor()

            if temp is not None and humidity is not None:
                send_to_supabase(temp, humidity)
            else:
                log(WARN, "Skipping Supabase upload — no valid sensor data")

            # Print stats every 10 loops
            if loop_count % 10 == 0:
                log_stats()

            log(DEBUG, "Sleeping {}s until next reading...".format(READING_INTERVAL))
            time.sleep(READING_INTERVAL)

        except KeyboardInterrupt:
            log(INFO, "Stopped by user (Ctrl-C)")
            log_stats()
            break

        except Exception as e:
            log(ERROR, "Unhandled error in main loop: {}".format(e))
            log(WARN, "Retrying in 5s...")
            time.sleep(5)


# ─────────────────────────────────────────
if __name__ == "__main__":
    main()
