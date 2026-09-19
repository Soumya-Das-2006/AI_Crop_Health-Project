# features/services/farming_advisory.py
from datetime import datetime, timedelta
from typing import Dict, List, Any

class FarmingAdvisory:
    @staticmethod
    def get_advisory(weather_data: Dict[str, Any], city: str = "Bhainsdehi Tahsil") -> List[Dict[str, Any]]:
        """Generate comprehensive farming advisory based on weather conditions"""
        try:
            current = weather_data['current']
            forecast = weather_data['daily']
            
            advisories = []
            
            # 1. Check conditions for harvest
            is_good_for_harvest = FarmingAdvisory._check_harvest_conditions(current, forecast)
            if is_good_for_harvest:
                advisories.append({
                    'title': 'Harvest Planning',
                    'message': f'Favorable conditions for harvest expected in the coming days. '
                              f'Wind speeds are moderate and rain chances are low.',
                    'risk': 'Low',
                    'icon': '🌾',
                    'valid_until': (datetime.now() + timedelta(days=7)).strftime('%m/%d/%Y')
                })
            
            # 2. Check for heat stress
            has_heat_stress = FarmingAdvisory._check_heat_stress(current, forecast)
            if has_heat_stress:
                advisories.append({
                    'title': 'Heat Stress Warning',
                    'message': 'High temperatures detected. Consider scheduling irrigation '
                              'in early morning or late evening. Avoid fieldwork during peak hours.',
                    'risk': 'High',
                    'icon': '🔥',
                    'valid_until': (datetime.now() + timedelta(days=2)).strftime('%m/%d/%Y')
                })
            
            # 3. Check for frost risk
            has_frost_risk = FarmingAdvisory._check_frost_risk(forecast)
            if has_frost_risk:
                advisories.append({
                    'title': 'Frost Risk Advisory',
                    'message': 'Low temperatures expected. Protect sensitive crops with frost covers. '
                              'Consider delaying planting of frost-sensitive varieties.',
                    'risk': 'Medium',
                    'icon': '❄️',
                    'valid_until': (datetime.now() + timedelta(days=3)).strftime('%m/%d/%Y')
                })
            
            # 4. Check for irrigation need
            needs_irrigation = FarmingAdvisory._check_irrigation_need(current, forecast)
            if needs_irrigation:
                advisories.append({
                    'title': 'Irrigation Recommended',
                    'message': 'Dry conditions detected. Optimal time for irrigation to '
                              'maintain soil moisture and support crop growth.',
                    'risk': 'Low',
                    'icon': '💧',
                    'valid_until': (datetime.now() + timedelta(days=1)).strftime('%m/%d/%Y')
                })
            
            # 5. Get quick text advisories (from the second class approach)
            quick_advisories = FarmingAdvisory._get_quick_advisories(current, weather_data)
            if quick_advisories:
                for i, advisory_text in enumerate(quick_advisories):
                    advisories.append({
                        'title': f'Quick Advisory {i+1}',
                        'message': advisory_text,
                        'risk': 'Low',
                        'icon': '💡',
                        'valid_until': (datetime.now() + timedelta(days=1)).strftime('%m/%d/%Y')
                    })
            
            # 6. Default advisory if none apply
            if not advisories:
                advisories.append({
                    'title': 'Normal Farming Conditions',
                    'message': 'Weather conditions are within normal ranges for farming activities. '
                              'Continue with regular farming schedule.',
                    'risk': 'Low',
                    'icon': '✅',
                    'valid_until': (datetime.now() + timedelta(days=1)).strftime('%m/%d/%Y')
                })
            
            # Return only top advisories (max 5)
            return advisories[:5]
            
        except Exception as e:
            # Return a default advisory in case of error
            return [{
                'title': 'Advisory System Error',
                'message': 'Unable to generate specific advisories. Please check weather data availability.',
                'risk': 'Medium',
                'icon': '⚠️',
                'valid_until': (datetime.now() + timedelta(days=1)).strftime('%m/%d/%Y')
            }]
    
    @staticmethod
    def _check_harvest_conditions(current: Dict, forecast: List) -> bool:
        """Check if conditions are good for harvesting"""
        if not current or not forecast:
            return False
        
        # Check wind speed
        wind_speed = current.get('wind_speed', 0)
        if wind_speed >= 15:  # km/h
            return False
        
        # Check humidity
        humidity = current.get('humidity', 50)
        if humidity >= 70:
            return False
        
        # Check precipitation in next 3 days
        if len(forecast) >= 3:
            for day in forecast[:3]:
                precip = day.get('precip', 0)  # precipitation in percentage or mm
                if precip >= 30:
                    return False
        
        return True
    
    @staticmethod
    def _check_heat_stress(current: Dict, forecast: List) -> bool:
        """Check for heat stress conditions"""
        if not current or not forecast:
            return False
        
        # Check current temperature
        if current.get('temp', 0) > 35:
            return True
        
        # Check forecast temperatures
        if len(forecast) >= 3:
            for day in forecast[:3]:
                temp_max = day.get('temp_max', 0)
                if temp_max > 38:
                    return True
        
        return False
    
    @staticmethod
    def _check_frost_risk(forecast: List) -> bool:
        """Check for frost risk conditions"""
        if not forecast or len(forecast) < 3:
            return False
        
        # Check minimum temperatures in next 3 days
        for day in forecast[:3]:
            temp_min = day.get('temp_min', 10)
            if temp_min < 5:
                return True
        
        return False
    
    @staticmethod
    def _check_irrigation_need(current: Dict, forecast: List) -> bool:
        """Check if irrigation is needed"""
        if not current or not forecast:
            return False
        
        # Check current conditions
        if current.get('temp', 0) > 30 and current.get('humidity', 0) < 50:
            return True
        
        # Check precipitation in next 5 days
        if len(forecast) >= 5:
            low_precip_days = 0
            for day in forecast[:5]:
                precip = day.get('precip', 0)
                if precip < 10:  # Less than 10mm precipitation
                    low_precip_days += 1
            
            if low_precip_days >= 4:  # 4 out of 5 days with low precipitation
                return True
        
        return False
    
    @staticmethod
    def _get_quick_advisories(current: Dict, weather_data: Dict) -> List[str]:
        """Generate quick text advisories (from the second approach)"""
        advisories = []
        
        current_temp = current.get('temp', 0)
        humidity = current.get('humidity', 50)
        description = current.get('description', '').lower()
        uv_index = weather_data.get('uv_index', 0)
        
        # Temperature-based advisories
        if current_temp > 35:
            advisories.append("High temperature alert! Consider irrigation during cooler hours.")
        elif current_temp < 15:
            advisories.append("Low temperature warning. Protect sensitive crops with covers.")
        
        # Humidity-based advisories
        if humidity > 80:
            advisories.append("High humidity detected. Watch for fungal diseases and improve ventilation.")
        elif humidity < 40:
            advisories.append("Low humidity. Consider mulching to retain soil moisture.")
        
        # Weather condition advisories
        if 'rain' in description:
            advisories.append("Rain expected. Postpone pesticide application.")
        if 'clear' in description or 'sunny' in description:
            advisories.append("Sunny weather. Good for drying crops and harvesting.")
        if 'cloud' in description:
            advisories.append("Cloudy conditions. Suitable for transplanting seedlings.")
        
        # UV Index advisory
        if uv_index > 7:
            advisories.append("High UV index. Provide shade for sensitive plants.")
        
        # Seasonal advice
        current_month = datetime.now().month
        if current_month in [6, 7, 8, 9]:
            advisories.append("Kharif season: Good time for rice, maize, cotton sowing.")
        elif current_month in [10, 11, 12, 1, 2, 3]:
            advisories.append("Rabi season: Suitable for wheat, barley, mustard crops.")
        else:
            advisories.append("Zaid season: Consider vegetables like cucumber, watermelon.")
        
        return advisories[:3]  # Return top 3 quick advisories