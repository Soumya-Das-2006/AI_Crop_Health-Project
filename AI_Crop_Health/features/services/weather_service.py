import requests
from django.conf import settings
from datetime import datetime, timedelta
from collections import defaultdict, Counter


class WeatherService:
    def __init__(self):
        self.api_key = settings.OPENWEATHER_API_KEY
        self.base_url = "https://api.openweathermap.org/data/2.5"

    # -----------------------------
    # GEO CODING
    # -----------------------------
    def get_coordinates(self, city):
        try:
            response = requests.get(
                "https://api.openweathermap.org/geo/1.0/direct",
                params={"q": city, "limit": 1, "appid": self.api_key},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            if data:
                return data[0]["lat"], data[0]["lon"], data[0].get("country", "IN")
        except Exception as e:
            print("Geo error:", e)

        # Default fallback
        return 23.6102, 77.3536, "IN"

    # -----------------------------
    # CURRENT WEATHER
    # -----------------------------
    def get_current_weather(self, lat, lon):
        try:
            response = requests.get(
                f"{self.base_url}/weather",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": self.api_key,
                    "units": "metric"
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print("Current weather error:", e)
            return None

    # -----------------------------
    # FORECAST (5 DAY)
    # -----------------------------
    def get_forecast_data(self, lat, lon):
        try:
            response = requests.get(
                f"{self.base_url}/forecast",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": self.api_key,
                    "units": "metric",
                    "cnt": 40
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print("Forecast error:", e)
            return None

    # -----------------------------
    # ONECALL (HOURLY / DAILY)
    # -----------------------------
    def get_onecall_data(self, lat, lon):
        try:
            response = requests.get(
                "https://api.openweathermap.org/data/3.0/onecall",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": self.api_key,
                    "units": "metric",
                    "exclude": "minutely"
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            try:
                response = requests.get(
                    f"{self.base_url}/onecall",
                    params={
                        "lat": lat,
                        "lon": lon,
                        "appid": self.api_key,
                        "units": "metric",
                        "exclude": "minutely"
                    },
                    timeout=10
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print("OneCall error:", e)
                return None

    # -----------------------------
    # MAIN ENTRY (CITY OR GPS)
    # -----------------------------
    def get_weather_data(self, city=None, lat=None, lon=None):
        try:
            # GPS HAS PRIORITY
            if lat and lon:
                lat = float(lat)
                lon = float(lon)
                city = city or "Your Location"
            else:
                city = city or "Bhainsdehi Tahsil, IN"
                lat, lon, _ = self.get_coordinates(city)

            current = self.get_current_weather(lat, lon)
            if not current:
                return self.get_sample_data()

            onecall = self.get_onecall_data(lat, lon)
            forecast = self.get_forecast_data(lat, lon)

            return self.process_weather_data(current, onecall, forecast)

        except Exception as e:
            print("Weather service error:", e)
            return self.get_sample_data()

    # -----------------------------
    # DATA PROCESSING
    # -----------------------------
    def process_weather_data(self, current, onecall, forecast):
        # Hourly
        hourly = []
        if onecall and "hourly" in onecall:
            for h in onecall["hourly"][:8]:
                hourly.append({
                    "time": datetime.fromtimestamp(h["dt"]).strftime("%I:%M %p").lstrip("0"),
                    "temp": round(h["temp"]),
                    "description": h["weather"][0]["main"],
                    "icon": h["weather"][0]["icon"]
                })
        elif forecast:
            for h in forecast["list"][:5]:
                hourly.append({
                    "time": datetime.fromtimestamp(h["dt"]).strftime("%I:%M %p").lstrip("0"),
                    "temp": round(h["main"]["temp"]),
                    "description": h["weather"][0]["main"],
                    "icon": h["weather"][0]["icon"]
                })

        # Daily
        daily = []
        if onecall and "daily" in onecall:
            for d in onecall["daily"][:5]:
                daily.append({
                    "day": datetime.fromtimestamp(d["dt"]).strftime("%A"),
                    "date": datetime.fromtimestamp(d["dt"]).strftime("%d/%m"),
                    "temp_min": round(d["temp"]["min"]),
                    "temp_max": round(d["temp"]["max"]),
                    "description": d["weather"][0]["main"],
                    "precip": int(d.get("pop", 0) * 100),
                    "icon": d["weather"][0]["icon"]
                })
        elif forecast:
            temps = defaultdict(list)
            weather = defaultdict(list)
            for i in forecast["list"]:
                day = datetime.fromtimestamp(i["dt"]).strftime("%Y-%m-%d")
                temps[day].append(i["main"]["temp"])
                weather[day].append(i["weather"][0])

            for idx, day in enumerate(list(temps.keys())[:5]):
                w = Counter([x["main"] for x in weather[day]]).most_common(1)[0][0]
                icon = Counter([x["icon"] for x in weather[day]]).most_common(1)[0][0]
                daily.append({
                    "day": "Today" if idx == 0 else datetime.strptime(day, "%Y-%m-%d").strftime("%A"),
                    "date": datetime.strptime(day, "%Y-%m-%d").strftime("%d/%m"),
                    "temp_min": round(min(temps[day])),
                    "temp_max": round(max(temps[day])),
                    "description": w,
                    "precip": 0,
                    "icon": icon
                })

        return {
            "current": {
                "temp": round(current["main"]["temp"]),
                "feels_like": round(current["main"]["feels_like"]),
                "humidity": current["main"]["humidity"],
                "pressure": current["main"]["pressure"],
                "wind_speed": round(current["wind"]["speed"] * 3.6),
                "wind_deg": current["wind"].get("deg", 0),
                "description": current["weather"][0]["main"],
                "icon": current["weather"][0]["icon"],
                "visibility": current.get("visibility", 10000) / 1000
            },
            "hourly": hourly or self.get_sample_hourly(),
            "daily": daily or self.get_sample_daily(),
            "alerts": onecall.get("alerts", []) if onecall else [],
            "uv_index": round(onecall["current"]["uvi"]) if onecall and "current" in onecall else 5,
            "sunrise": datetime.fromtimestamp(current["sys"]["sunrise"]),
            "sunset": datetime.fromtimestamp(current["sys"]["sunset"]),
            "coordinates": current["coord"]
        }

    # -----------------------------
    # FALLBACK DATA
    # -----------------------------
    def get_sample_hourly(self):
        now = datetime.now()
        return [{
            "time": (now + timedelta(hours=i)).strftime("%I:%M %p").lstrip("0"),
            "temp": 20 + i,
            "description": "Clear",
            "icon": "01d"
        } for i in range(8)]

    def get_sample_daily(self):
        now = datetime.now()
        return [{
            "day": (now + timedelta(days=i)).strftime("%A"),
            "date": (now + timedelta(days=i)).strftime("%d/%m"),
            "temp_min": 18 + i,
            "temp_max": 28 + i,
            "description": "Clear",
            "precip": 0,
            "icon": "01d"
        } for i in range(5)]

    def get_sample_data(self):
        return {
            "current": {
                "temp": 25,
                "feels_like": 24,
                "humidity": 50,
                "pressure": 1012,
                "wind_speed": 6,
                "wind_deg": 180,
                "description": "Clear",
                "icon": "01d",
                "visibility": 10
            },
            "hourly": self.get_sample_hourly(),
            "daily": self.get_sample_daily(),
            "alerts": [],
            "uv_index": 6,
            "sunrise": datetime.now(),
            "sunset": datetime.now(),
            "coordinates": {"lat": 23.61, "lon": 77.35}
        }
