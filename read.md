# ESP32 + MicroPython Live Climate Dashboard

A real-time temperature and humidity monitoring system utilizing an **ESP32**, **DHT11 sensor**, and **MicroPython**. Data is logged directly into a **Supabase** backend via its REST API, which can then be visualized instantly on a live dashboard.

---

## 🚀 Features
* **Live Climate Tracking:** Reads temperature and humidity data at regular intervals using the DHT11 sensor.
* **Serverless Database Backend:** Sends payload data directly to **Supabase** over HTTPS (no middleman server required).
* **Robust Network Handling:** Automatically connects to Wi-Fi on boot and includes exception handling for sensor read failures or network drops.
* **Lightweight Firmware:** Built entirely on **MicroPython** using the **Thonny IDE**.

---

## 🛠️ Hardware Requirements
* **ESP32** Development Board
* **DHT11** Temperature & Humidity Sensor
* **Breadboard** and Jumper Wires
* **Micro-USB Cable** (data-capable)

### Wiring Diagram
Connect your DHT11 sensor to the ESP32 using the following typical pinout configuration:

| DHT11 Pin | ESP32 Pin | Notes |
| :--- | :--- | :--- |
| **VCC** | `3V3` or `5V` | Check your specific sensor module rating |
| **GND** | `GND` | Ground |
| **DATA** | `GPIO 23` | Can be adjusted in `main.py` |

---

## 💾 Software & Backend Setup

### 1. Supabase Configuration
1. Create a free account at [Supabase](https://supabase.com).
2. Create a new project and navigate to the **Table Editor**.
3. Create a table named `climate_data` with the following schema:

| Column Name | Data Type | Default / Settings |
| :--- | :--- | :--- |
| `id` | `int8` | Primary Key (Autoincrement) |
| `created_at` | `timestamptz` | `now()` |
| `temperature` | `float4` | Allow Null |
| `humidity` | `float4` | Allow Null |

4. Go to **Project Settings -> API** and copy your **Project URL** and **anon public API key**.

### 2. Environment Variables
Create a file named `config.py` in your MicroPython environment to store your credentials securely:

```python
# config.py
WIFI_SSID = "Your_WiFi_Name"
WIFI_PASSWORD = "Your_WiFi_Password"

SUPABASE_URL = "[https://your-project-id.supabase.co](https://your-project-id.supabase.co)"
SUPABASE_KEY = "your-anon-public-key-here"
