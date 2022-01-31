import json
from fastapi import FastAPI
import requests
import numpy as np
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import plotly.io as io
import csv
import base64

app = FastAPI()


@app.get("/")
async def root():
    return {
        "success": True,
        "message": "Connection available",
        "data": []
    }


@app.get("/get_recommendation/{symbol}/{interval}/{entry}")
async def root(symbol: str, interval: str, entry: float):
    market = symbol
    tick_interval = interval
    price = entry
    url = 'https://api.binance.com/api/v3/klines?symbol=' + market + '&interval=' + tick_interval
    data = requests.get(url).json()
    # open the file in the write mode
    f = open('result.csv', 'w')
    # create the csv writer
    writer = csv.writer(f)
    title = [
        'OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 'CloseTime', 'QuoteVolume', 'Trades', 'TakerBase',
        'TakerQuote', 'Ignore'
    ]
    # write a row to the csv file
    writer.writerow(title)
    for candle in data:
        single_data = [
            str(datetime.fromtimestamp(candle[0] / 1000).strftime('%d-%m-%y %H:%M')),
            str(candle[1]),
            str(candle[2]),
            str(candle[3]),
            str(candle[4]),
            str(candle[5]),
            str(datetime.fromtimestamp(candle[6] / 1000).strftime('%d-%m-%Y')) if tick_interval == '1d' else str(
                datetime.fromtimestamp(candle[6] / 1000).strftime('%d-%m-%Y %H:%M')),
            str(candle[7]),
            str(candle[8]),
            str(candle[9]),
            str(candle[10]),
            str(candle[11]),
        ]
        writer.writerow(single_data)

        # close = candle[4]
        # timestamp = candle[6]/1000
        # date_time = datetime.fromtimestamp(timestamp).strftime('%d-%m-%y %H:%M')
        # full_candle = [
        #     date_time,
        #     close,
        # ]
        # result.append(full_candle)

    # close the file
    f.close()
    #
    df = pd.read_csv('result.csv')
    # df['vwap'] = df['QuoteVolume'] / df['Volume']
    df['ma_20'] = df.rolling(window=20)['Close'].mean()
    df['ma_50'] = df.rolling(window=50)['Close'].mean()
    df['diff'] = df['ma_20'] - df['ma_50']
    df['mirror_ma_50'] = df['ma_20'] + df['diff']
    # calculate take profit
    df['take_profit'] = df[['mirror_ma_50', 'ma_50']].max(axis=1)
    df['take_profit_percent'] = abs((df['take_profit'] - price) / price * 100)
    # calculate buy back
    df['buy_back'] = df[['mirror_ma_50', 'ma_50']].min(axis=1)
    df['buy_back_percent'] = abs((df['buy_back'] - price) / price * 100)
    # calculate entry price
    df['entry_price'] = df['ma_20']
    # calculate earning callback
    df['earning_callback'] = df['take_profit'] - (0.1 * (df['take_profit'] - df['entry_price']))
    df['earning_callback_percent'] = abs((df['earning_callback'] - df['take_profit']) / df['take_profit'] * 100)
    # calculate buy in callback
    df['buy_in_callback'] = df['buy_back'] + (0.1 * ((df['entry_price']) - df['buy_back']))
    df['buy_in_callback_percent'] = abs((df['buy_in_callback'] - df['buy_back']) / df['buy_back'] * 100)

    print(df[['ma_20', 'ma_50', 'diff', 'mirror_ma_50', 'market_bullish', 'take_profit', 'take_profit_percent', 'buy_back',
              'buy_back_percent', 'entry_price', 'earning_callback', 'earning_callback_percent', 'buy_in_callback',
              'buy_in_callback_percent']])

    fig = go.Figure(data=[go.Candlestick(x=df['CloseTime'],
                                         open=df['Open'],
                                         high=df['High'],
                                         low=df['Low'],
                                         close=df['Close'])])

    fig.add_trace(go.Scatter(
        x=df['CloseTime'],
        y=df['ma_20'],
        name='MA-20',  # Style name/legend entry with html tags
        connectgaps=True  # override default to connect the gaps
    ))

    fig.add_trace(go.Scatter(
        x=df['CloseTime'],
        y=df['ma_50'],
        name='MA-50',  # Style name/legend entry with html tags
        connectgaps=True  # override default to connect the gaps
    ))

    fig.add_trace(go.Scatter(
        x=df['CloseTime'],
        y=df['mirror_ma_50'],
        name='Mirror MA-50',  # Style name/legend entry with html tags
        connectgaps=True  # override default to connect the gaps
    ))

    image = io.to_image(fig, 'png', 2000, 1000)
    base64_image = base64.b64encode(image)

    return {
        "success": True,
        "message": "Request Accepted",
        "data": {
            "entry_price": df['entry_price'].iloc[-1],
            "take_profit": df['take_profit_percent'].iloc[-1],
            "earning_callback": df['earning_callback_percent'].iloc[-1],
            "buy_back": df['buy_back_percent'].iloc[-1],
            "buy_in_callback": df['buy_in_callback_percent'].iloc[-1],
        },
        "additional_data": {
            "ma_20": df['ma_20'].iloc[-1],
            "ma_50": df['ma_50'].iloc[-1],
            "mirror_ma_50": df['mirror_ma_50'].iloc[-1],
            "market_trend": "Bullish" if df['ma_20'].iloc[-1] > df['ma_50'].iloc[-1] else "Bearish",
            "status": "Recommended" if price < df['entry_price'].iloc[-1] else "Not Recommended"
        },
        "image": base64_image
    }
