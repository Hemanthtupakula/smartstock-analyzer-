# app.py
# SmartStock Analyzer Pro – Live Indian Stocks & Crypto Dashboard
# 100% Original Project by T Hemanth Kumar | MCA Final Year Student
# Deploy on: https://share.streamlit.io → Just upload this file!

import streamlit as st
import yfinance as yf
import requests
import plotly.graph_objects as go
from datetime import datetime

# ==================== PAGE CONFIG & DESIGN ====================
st.set_page_config(
    page_title="SmartStock Analyzer Pro - T Hemanth Kumar",
    page_icon="₹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling – Your Branding
st.markdown("""
<style>
    .main {background-color: #0e1117; color: #ffffff;}
    .css-1d391kg {padding-top: 1rem;}
    .title {font-size: 52px; font-weight: bold; text-align: center; 
            background: linear-gradient(90deg, #00D4FF, #66FF99); 
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
    .subtitle {text-align: center; font-size: 22px; color: #A0D8FF;}
    .footer {text-align: center; margin-top: 60px; color: #66FF99; font-size: 14px;}
    .stButton>button {background-color: #00D4FF; color: black; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="title">SmartStock Analyzer Pro</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Real-Time Indian Stocks & Crypto Tracker with Full Company Analysis<br>Built by T Hemanth Kumar (MCA Final Year)</p>', unsafe_allow_html=True)

# ==================== SEARCH SYMBOL FUNCTION ====================
@st.cache_data(ttl=3600)
def search_company(query):
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=6&newsCount=0"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json().get("quotes", [])
        for item in data:
            sym = item.get("symbol")
            if sym and (sym.endswith(".NS") or sym.endswith(".BO") or sym.endswith("-USD")):
                return sym, item.get("shortname") or item.get("longname")
        return data[0]["symbol"], data[0].get("shortname") if data else (None, None)
    except:
        return None, None

# ==================== FETCH FULL DATA ====================
def get_full_analysis(symbol):
    ticker = yf.Ticker(symbol)
    info = ticker.info
    hist = ticker.history(period="60d")
    
    if hist.empty:
        return None, None
    
    current = info.get("currentPrice") or info.get("regularMarketPrice")
    prev_close = info.get("previousClose", 0)
    change = current - prev_close if prev_close else 0
    pct_change = (change / prev_close) * 100 if prev_close else 0

    return {
        "info": info,
        "current_price": current,
        "change": change,
        "pct_change": pct_change,
        "history": hist
    }, ticker

# ==================== MAIN APP ====================
with st.sidebar:
    st.header("Search Any Company")
    query = st.text_input("Enter name (e.g., Reliance, TCS, Bitcoin, Zomato)", placeholder="Type here...")
    st.caption("Supports Indian stocks (.NS), BSE (.BO), and Cryptocurrencies")

if st.button("Analyze Stock", type="primary", use_container_width=True):
    if query:
        with st.spinner("Searching company..."):
            symbol, name = search_company(query)
            
        if not symbol:
            st.error("Company not found! Try exact name or symbol (e.g., RELIANCE.NS)")
        else:
            with st.spinner("Fetching live data & analysis..."):
                result, ticker = get_full_analysis(symbol)
                if not result:
                    st.error("No data available. Try again later.")
                else:
                    info = result["info"]
                    st.success(f"Found: {info.get('longName', name)} ({symbol})")

                    # === PRICE CARD ===
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Current Price", 
                                f"₹{result['current_price']:,.2f}" if 'NS' in symbol else f"${result['current_price']:,.4f}")
                    with col2:
                        st.metric("Change Today", 
                                f"{result['change']:+.2f} ({result['pct_change']:+.2f}%)",
                                delta=f"{result['change']:+.2f} ({result['pct_change']:+.2f}%)")
                    with col3:
                        st.metric("Market Cap", f"₹{info.get('marketCap',0):,}")
                    with col4:
                        st.metric("Volume", f"{info.get('volume',0):,}")

                    # === PRICE CHART ===
                    st.subheader("60-Day Price Movement")
                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(
                        x=result["history"].index,
                        open=result["history"]['Open'],
                        high=result["history"]['High'],
                        low=result["history"]['Low'],
                        close=result["history"]['Close'],
                        name="OHLC"
                    ))
                    fig.add_trace(go.Scatter(x=result["history"].index, y=result["history"]['Close'],
                                           mode='lines', name='Close Price', line=dict(color='#00D4FF')))
                    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)

                    # === COMPANY DETAILS ===
                    st.subheader("Complete Company Profile")
                    c1, c2, c3 = st.columns(3)
                    details = [
                        ("Sector", info.get("sector")),
                        ("Industry", info.get("industry")),
                        ("P/E Ratio", info.get("trailingPE")),
                        ("EPS (TTM)", info.get("trailingEps")),
                        ("Dividend Yield", f"{info.get('dividendYield',0)*100:.2f}%" if info.get('dividendYield') else "N/A"),
                        ("52W High", f"₹{info.get('fiftyTwoWeekHigh',0):,.2f}"),
                        ("52W Low", f"₹{info.get('fiftyTwoWeekLow',0):,.2f}"),
                        ("Beta", info.get("beta")),
                        ("Website", info.get("website")),
                        ("Employees", info.get("fullTimeEmployees")),
                    ]
                    for i, (label, value) in enumerate(details):
                        with [c1, c2, c3][i % 3]:
                            st.write(f"**{label}**")
                            st.write(value or "N/A")

                    st.info(info.get("longBusinessSummary", "No description available")[:1000])

    else:
        st.warning("Please enter a company name!")

# ==================== FOOTER ====================
st.markdown("""
<div class="footer">
    <hr>
    <p><strong>SmartStock Analyzer Pro v2.0</strong> – 100% Built from Scratch by <strong>T Hemanth Kumar</strong></p>
    <p>MCA Final Year | Stock Data Analyst | Full-Stack Developer</p>
    <p>GitHub: github.com/yourusername • LinkedIn: linkedin.com/in/yourprofile</p>
    <p>Deployed on Streamlit Cloud • Open Source & Free Forever</p>
</div>
""", unsafe_allow_html=True)