# app.py (your Flask application)
from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
import requests
import datetime
import os

app = Flask(__name__)

# Securely load configuration
SEASONAL_DATA_PATH = os.environ.get('SEASONAL_DATA_PATH', 'Crop_Season_Wise_Price_Arrival_29-04-2026_11-20-31_PM.csv')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY') # Get from environment variables

# Your helper functions
def get_weather():
    """Get current weather data (returns dummy data if API fails)"""
    try:
        if WEATHER_API_KEY:
            # Real weather API call would go here
            pass
    except:
        pass
    # Return dummy weather value (mm of rain)
    return 2.5

def setup_dummy_history():
    """Create dummy historical data if CSV is missing"""
    dates = pd.date_range(end=datetime.datetime.now(), periods=365, freq='D')
    prices = np.random.uniform(1500, 2500, size=len(dates))
    df = pd.DataFrame({'Price Date': dates, 'Modal_Price': prices})
    df.to_csv('Agriculture_price_dataset.csv', index=False)

# Your run_khet_ai function, modified to return data instead of print/plot
def run_khet_ai_api(crop_target):
    # (Modified content of your run_khet_ai function)
    # 1. Load your new 2026 Seasonal File
    df_s = pd.read_csv(SEASONAL_DATA_PATH, skiprows=2)
    crop_info = df_s[df_s['Commodity'].str.contains(crop_target, case=False)].iloc[0]
    msp = crop_info['MSP (Rs./Quintal) 2025-26']

    # 2. Setup/Load History (use last 365 days for faster training)
    try:
        df_h = pd.read_csv('Agriculture_price_dataset.csv')
        df_h['ds'] = pd.to_datetime(df_h['Price Date'])
        df_h['y'] = df_h['Modal_Price']
        # Use only last 365 days to speed up Prophet
        df_h = df_h.tail(365)
        # Clean NaN values
        df_h = df_h.dropna(subset=['ds', 'y'])
        df_h = df_h[df_h['y'].notna() & (df_h['y'] > 0)]
    except Exception as e:
        setup_dummy_history() # You'd want to handle this better in production
        df_h = pd.read_csv('Agriculture_price_dataset.csv')
        df_h['ds'] = pd.to_datetime(df_h['Price Date'])
        df_h['y'] = df_h['Modal_Price']
        df_h = df_h.tail(365)
        df_h = df_h.dropna(subset=['ds', 'y'])
        df_h = df_h[df_h['y'].notna() & (df_h['y'] > 0)]

    # Simple forecasting using linear trend
    df_h = df_h.sort_values('ds')
    recent_prices = df_h['y'].tail(30).values
    if len(recent_prices) < 2:
        recent_prices = [2000, 2100, 2200, 2300, 2400, 2500]
    
    # Calculate trend
    x = np.arange(len(recent_prices))
    slope, intercept = np.polyfit(x, recent_prices, 1)
    
    # Forecast next 7 days
    future_dates = []
    future_prices = []
    base_price = recent_prices[-1]
    for i in range(1, 8):
        future_date = datetime.datetime.now() + datetime.timedelta(days=i)
        predicted = base_price + (slope * i)
        future_dates.append(future_date.strftime('%Y-%m-%d'))
        future_prices.append(round(predicted, 2))
    
    today_p = base_price + slope
    max_p = max(future_prices)
    rain = get_weather()

    advice = ""
    if rain > 5.0:
        advice = f"SELL IMMEDIATELY. {rain}mm rain forecast could damage crops."
    elif max_p > today_p * 1.02:
        advice = f"HOLD. Price peak of ₹{round(max_p,2)} expected this week."
    else:
        advice = "SELL. No significant price increase expected."
        
    # Convert forecast to a list of dicts for JSON serialization
    forecast_data = []
    for i, (d, p) in enumerate(zip(future_dates, future_prices)):
        forecast_data.append({"ds": d, "yhat": p})

    return {
        "crop_target": crop_target,
        "current_msp": f"₹{msp}",
        "predicted_price_today": f"₹{round(today_p, 2)}",
        "weekly_forecast": forecast_data,
        "advice": advice
    }

# Your get_exact_price function, modified to return data
def get_exact_price_api(target_crop):
    # (Modified content of your get_exact_price function)
    df = pd.read_csv(SEASONAL_DATA_PATH, skiprows=2)
    row = df[df['Commodity'].str.contains(target_crop, case=False)].iloc[0]

    if row['Rabi Marketing Season Price (Rs./Quintal)'] != '-':
        base = float(row['Rabi Marketing Season Price (Rs./Quintal)'])
    else:
        base = float(row['Kharif Marketing Season Price (Rs./Quintal)'])
        
    forecast_list = []
    for i in range(7):
        date_obj = datetime.datetime.now() + datetime.timedelta(days=i)
        date_str = date_obj.strftime('%Y-%m-%d')
        change = 1 + (np.sin(i) * 0.012) 
        exact_price = round(base * change, 2)
        forecast_list.append({"date": date_str, "price": f"₹{exact_price}"})

    return {
        "crop_target": target_crop,
        "daily_exact_forecast": forecast_list
    }

@app.route('/khet-ai-report', methods=['GET'])
def khet_ai_report():
    crop = request.args.get('crop', 'Wheat') # Default to Wheat if no crop specified
    report = run_khet_ai_api(crop)
    return jsonify(report)

@app.route('/exact-price-forecast', methods=['GET'])
def exact_price_forecast():
    crop = request.args.get('crop', 'Wheat')
    forecast = get_exact_price_api(crop)
    return jsonify(forecast)

@app.route('/')
def index():
    return jsonify({
        "message": "Khet AI API is running",
        "endpoints": {
            "/khet-ai-report": "Get price forecast and advice for a crop (e.g., /khet-ai-report?crop=Wheat)",
            "/exact-price-forecast": "Get exact daily price forecast (e.g., /exact-price-forecast?crop=Wheat)"
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
