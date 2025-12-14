import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
import pytz

# --- Konfigurasi Halaman ---
st.set_page_config(page_title="Gold Sniper Pro (1:3)", layout="wide")

st.title("🏆 Gold Sniper Pro (Trend + RSI Filter)")
st.markdown("""
Aplikasi ini telah ditala mengikut strategi **Trend Following**:
1. **Trend Filter:** EMA 50 & EMA 200.
2. **Entry:** RSI Pullback (Oversold semasa Uptrend / Overbought semasa Downtrend).
3. **Exit:** Ratio Risk:Reward **1:3**.
""")

# --- Sidebar ---
st.sidebar.header("Tetapan Carta")
timeframe_option = st.sidebar.selectbox(
    "Pilih Timeframe:", 
    ["1h (1 Jam)", "1d (Sehari)"], 
    index=0
)

# Mapping pilihan
interval_map = {"1h (1 Jam)": "1h", "1d (Sehari)": "1d"}
selected_interval = interval_map[timeframe_option]

# Logic Period
if selected_interval == "1h":
    period = "6mo"
    risk_buffer = 3.50 # $3.50 (35 pips) Risk untuk H1
else:
    period = "2y"
    risk_buffer = 15.00 # $15.00 (150 pips) Risk untuk Daily

# --- Fungsi Tarik Data ---
def get_gold_data(interval, period):
    ticker = "GC=F" 
    data = yf.download(ticker, period=period, interval=interval, progress=False)
    
    if data.empty:
        st.error("Data gagal ditarik. Pasaran mungkin tutup.")
        return None
    
    data.reset_index(inplace=True)
    # Fix MultiIndex columns issue
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0] for col in data.columns]
        
    kl_tz = pytz.timezone('Asia/Kuala_Lumpur')
    # Timezone conversion safety check
    if 'Datetime' in data.columns:
        if data['Datetime'].dt.tz is None:
             data['Datetime'] = data['Datetime'].dt.tz_localize('UTC').dt.tz_convert(kl_tz)
        else:
             data['Datetime'] = data['Datetime'].dt.tz_convert(kl_tz)
    elif 'Date' in data.columns:
        data['Datetime'] = pd.to_datetime(data['Date']) # Fallback for daily data
         
    return data

# --- Fungsi Indikator ---
def add_indicators(df):
    # RSI (Momentum)
    df["RSI"] = RSIIndicator(close=df["Close"], window=14).rsi()
    
    # EMA 50 & 200 (Trend Filter Wajib)
    df["EMA_50"] = EMAIndicator(close=df["Close"], window=50).ema_indicator()
    df["EMA_200"] = EMAIndicator(close=df["Close"], window=200).ema_indicator()
    
    return df

# --- Logik Signal Pintar (Strategy 1:3) ---
def analyze_signal(row, risk_amt):
    close_price = row['Close']
    rsi = row['RSI']
    ema50 = row['EMA_50']
    ema200 = row['EMA_200']
    
    signal_type = "NEUTRAL"
    reason = "Wait for Setup"
    sl = 0.0
    tp = 0.0
    
    # 1. Tentukan Trend
    is_uptrend = ema50 > ema200
    
    # 2. Logic Filter (Hanya Buy masa Uptrend, Sell masa Downtrend)
    if is_uptrend:
        if rsi < 35: # Pullback yang cantik
            signal_type = "BUY"
            reason = "UPTREND + RSI OVERSOLD (<35)"
            sl = close_price - risk_amt
            tp = close_price + (risk_amt * 3) # Ratio 1:3
        elif rsi > 70:
            signal_type = "WARNING"
            reason = "Price Overextended (Jangan Buy Pucuk)"
        else:
            reason = "Uptrend (Tunggu RSI Turun)"
            
    else: # Downtrend
        if rsi > 65: # Pullback naik atas
            signal_type = "SELL"
            reason = "DOWNTREND + RSI OVERBOUGHT (>65)"
            sl = close_price + risk_amt
            tp = close_price - (risk_amt * 3) # Ratio 1:3
        elif rsi < 30:
            signal_type = "WARNING"
            reason = "Price Oversold (Jangan Sell Akar)"
        else:
            reason = "Downtrend (Tunggu RSI Naik)"
            
    return signal_type, reason, sl, tp

# --- Main App Logic ---
data = get_gold_data(selected_interval, period)

if data is not None and not data.empty:
    data = add_indicators(data)
    
    last_row = data.iloc[-1]
    prev_row = data.iloc[-2]
    change = last_row['Close'] - prev_row['Close']
    
    # Dapatkan Signal Terkini
    sig_type, sig_reason, sig_sl, sig_tp = analyze_signal(last_row, risk_buffer)
    
    # Dashboard Utama
    col1, col2, col3 = st.columns([1, 1, 2])
    
    col1.metric("Harga Emas (USD)", f"${last_row['Close']:.2f}", f"{change:.2f}")
    
    # Warna RSI dinamik
    rsi_val = last_row['RSI']
    rsi_delta = rsi_val - prev_row['RSI']
    col2.metric("RSI (14)", f"{rsi_val:.2f}", f"{rsi_delta:.2f}")
    
    # Paparan Status Trend
    trend_now = "BULLISH 🐂" if last_row['EMA_50'] > last_row['EMA_200'] else "BEARISH 🐻"
    trend_color = "green" if last_row['EMA_50'] > last_row['EMA_200'] else "red"
    
    with col3:
        st.markdown(f"**Trend Semasa:** :{trend_color}[{trend_now}]")
        st.caption(f"Reason: {sig_reason}")

    # --- KOTAK SIGNAL (JIKA ADA) ---
    st.divider()
    
    if sig_type == "BUY":
        st.success(f"### 🟢 SIGNAL: STRONG BUY")
        c1, c2, c3 = st.columns(3)
        c1.metric("ENTRY", f"${last_row['Close']:.2f}")
        c2.metric("STOP LOSS (Risk)", f"${sig_sl:.2f}", f"-${risk_buffer:.2f}", delta_color="inverse")
        c3.metric("TAKE PROFIT (1:3)", f"${sig_tp:.2f}", f"+${risk_buffer*3:.2f}")
        st.info("Setup: Trend sedang naik (EMA50 > EMA200) dan harga buat 'discount' (RSI < 35).")
        
    elif sig_type == "SELL":
        st.error(f"### 🔴 SIGNAL: STRONG SELL")
        c1, c2, c3 = st.columns(3)
        c1.metric("ENTRY", f"${last_row['Close']:.2f}")
        c2.metric("STOP LOSS (Risk)", f"${sig_sl:.2f}", f"+${risk_buffer:.2f}", delta_color="inverse")
        c3.metric("TAKE PROFIT (1:3)", f"${sig_tp:.2f}", f"-${risk_buffer*3:.2f}")
        st.info("Setup: Trend sedang turun (EMA50 < EMA200) dan harga naik sementara (RSI > 65).")
        
    else:
        st.warning(f"### ⏸️ TIADA SIGNAL (WAIT)")
        st.write("Pasaran tidak memenuhi kriteria selamat (Trend + RSI) untuk entry 1:3 sekarang.")

    # --- Graf Candlestick ---
    st.subheader(f"Carta Analisis")
    
    fig = go.Figure()
    
    # Candle
    fig.add_trace(go.Candlestick(x=data['Datetime'],
                open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'],
                name='Price'))
    
    # EMA Lines
    fig.add_trace(go.Scatter(x=data['Datetime'], y=data['EMA_50'], line=dict(color='#2962FF', width=2), name='EMA 50 (Trend)'))
    fig.add_trace(go.Scatter(x=data['Datetime'], y=data['EMA_200'], line=dict(color='#FF6D00', width=2), name='EMA 200 (Baseline)'))

    # Entry/SL/TP Lines di Chart (Jika signal aktif)
    if sig_type in ["BUY", "SELL"]:
        fig.add_hline(y=sig_tp, line_dash="dash", line_color="green", annotation_text="TP (1:3)")
        fig.add_hline(y=sig_sl, line_dash="dash", line_color="red", annotation_text="SL")

    fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0))
    
    # Zoom auto
    fig.update_xaxes(range=[data['Datetime'].iloc[-80], data['Datetime'].iloc[-1]])

    st.plotly_chart(fig, use_container_width=True)

else:
    st.write("Menunggu data...")
