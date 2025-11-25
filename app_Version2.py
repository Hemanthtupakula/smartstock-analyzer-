# Flask app: fetch Indian tickers (sample), return prices + descriptions, updates every 5s in client
from flask import Flask, jsonify, request, render_template, send_from_directory
import yfinance as yf
import time
import threading
from functools import lru_cache
import os
import pandas as pd

app = Flask(__name__, template_folder='templates')

# Load default tickers from tickers.txt in repo or use sample list
DEFAULT_TICKERS_FILE = 'tickers.txt'
if os.path.exists(DEFAULT_TICKERS_FILE):
    with open(DEFAULT_TICKERS_FILE) as f:
        DEFAULT_TICKERS = [line.strip().upper() for line in f if line.strip() and not line.startswith('#')]
else:
    # A small sample (NSE suffix .NS). Add more tickers or replace file to include all.
    DEFAULT_TICKERS = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR",
        "ICICIBANK", "KOTAKBANK", "HDFC", "SBIN", "BHARTIARTL"
    ]

# Convert to yfinance symbols (NSE uses .NS)
def to_symbol(ticker):
    ticker = ticker.strip().upper()
    if ticker.endswith('.NS') or ticker.endswith('.BO'):
        return ticker
    return ticker + '.NS'

# Simple in-memory cache for company descriptions (refresh periodically)
company_info_cache = {}
company_info_lock = threading.Lock()
COMPANY_INFO_TTL = 60 * 60  # refresh every hour

def fetch_company_info(symbol):
    """Fetch and cache company description and name for symbol (yfinance symbol)"""
    now = time.time()
    with company_info_lock:
        entry = company_info_cache.get(symbol)
        if entry and now - entry.get('fetched_at', 0) < COMPANY_INFO_TTL:
            return entry['info']
        try:
            t = yf.Ticker(symbol)
            info = {}
            # try preferred fields
            info['name'] = info.get('name') or t.info.get('longName') or t.info.get('shortName') or symbol
            # long business summary if available
            desc = t.info.get('longBusinessSummary') or t.info.get('sector') or ''
            info['description'] = desc
        except Exception:
            info = {'name': symbol, 'description': ''}
        company_info_cache[symbol] = {'info': info, 'fetched_at': now}
        return info

def get_latest_prices(tickers):
    """Fetch latest close price (and percent change from previous close) for tickers list.
       Uses yf.download for batch efficiency. Returns dict keyed by original ticker (no .NS).
    """
    if not tickers:
        return {}
    # Prepare yfinance symbols
    sym_map = {}
    symbols = []
    for t in tickers:
        s = to_symbol(t)
        sym_map[s] = t.upper()
        symbols.append(s)

    # Use yfinance.download for batch query; using last 2 days for prev close
    try:
        data = yf.download(tickers=" ".join(symbols), period='2d', interval='1d', progress=False, threads=False)
        results = {}
        # Handling different return shapes for single vs multi tickers
        if data.empty:
            # fallback: query each ticker individually
            for s in symbols:
                try:
                    t = yf.Ticker(s)
                    hist = t.history(period='2d', interval='1d')
                    if hist is not None and not hist.empty:
                        latest = hist['Close'].iloc[-1]
                        prev = hist['Close'].iloc[-2] if len(hist) > 1 else latest
                        change_pct = round(((latest - prev) / prev) * 100, 2) if prev != 0 else 0.0
                        results[sym_map[s]] = {'price': round(float(latest), 4), 'change_pct': change_pct}
                except Exception:
                    results[sym_map[s]] = {'price': None, 'change_pct': None}
            return results
        # If single ticker, data is a Series/DataFrame without MultiIndex
        if isinstance(data.columns, pd.MultiIndex):
            # MultiTicker: columns like ('Close', 'RELIANCE.NS')
            for s in symbols:
                if ('Close', s) in data.columns:
                    series = data[('Close', s)].dropna()
                    if len(series) == 0:
                        results[sym_map[s]] = {'price': None, 'change_pct': None}
                        continue
                    latest = series.iloc[-1]
                    prev = series.iloc[-2] if len(series) > 1 else latest
                    change_pct = round(((latest - prev) / prev) * 100, 2) if prev != 0 else 0.0
                    results[sym_map[s]] = {'price': round(float(latest), 4), 'change_pct': change_pct}
                else:
                    results[sym_map[s]] = {'price': None, 'change_pct': None}
        else:
            # Single ticker returned as DataFrame with columns like ['Open','High','Low','Close','Volume']
            series = data['Close'].dropna()
            if len(series) == 0:
                results[sym_map[symbols[0]]] = {'price': None, 'change_pct': None}
            else:
                latest = series.iloc[-1]
                prev = series.iloc[-2] if len(series) > 1 else latest
                change_pct = round(((latest - prev) / prev) * 100, 2) if prev != 0 else 0.0
                results[sym_map[symbols[0]]] = {'price': round(float(latest), 4), 'change_pct': change_pct}
        return results
    except Exception:
        # fallback to per-ticker queries on error
        results = {}
        for s in symbols:
            try:
                t = yf.Ticker(s)
                hist = t.history(period='2d', interval='1d')
                if hist is not None and not hist.empty:
                    latest = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2] if len(hist) > 1 else latest
                    change_pct = round(((latest - prev) / prev) * 100, 2) if prev != 0 else 0.0
                    results[sym_map[s]] = {'price': round(float(latest), 4), 'change_pct': change_pct}
                else:
                    results[sym_map[s]] = {'price': None, 'change_pct': None}
            except Exception:
                results[sym_map[s]] = {'price': None, 'change_pct': None}
        return results

@app.route('/')
def index():
    # By default show first 100 tickers (configurable)
    display_count = int(request.args.get('count', 50))
    tickers = DEFAULT_TICKERS[:display_count]
    return render_template('index.html', tickers=tickers)

@app.route('/prices')
def prices():
    # Accept ?tickers=RELIANCE,TCS,INFY or ?count=50 to use defaults
    tickers_param = request.args.get('tickers')
    if tickers_param:
        tickers = [t.strip().upper() for t in tickers_param.split(',') if t.strip()]
    else:
        count = int(request.args.get('count', 50))
        tickers = DEFAULT_TICKERS[:count]

    # limit size to avoid abuse
    MAX = 200
    if len(tickers) > MAX:
        tickers = tickers[:MAX]

    price_data = get_latest_prices(tickers)

    # attach company info (cached)
    response = {}
    for t in tickers:
        sym = to_symbol(t)
        info = fetch_company_info(sym)
        pdict = price_data.get(t, {'price': None, 'change_pct': None})
        response[t] = {
            'symbol': sym,
            'name': info.get('name', t),
            'description': info.get('description', '')[:600],  # limit description size
            'price': pdict.get('price'),
            'change_pct': pdict.get('change_pct')
        }
    return jsonify(response)

if __name__ == '__main__':
    # development server
    app.run(host='0.0.0.0', port=5000, debug=True)