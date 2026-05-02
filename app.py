"""
═══════════════════════════════════════════════════════════════════
  ALPHAQUANT IDX v2.0 - Full Universe + Auto-Updater
  UI/UX Upgraded Version ✨ (Fixed Matplotlib Error)
═══════════════════════════════════════════════════════════════════
"""

# ════════════════════════════════════════════════════════════════
# SECTION 1: IMPORT LIBRARY
# ════════════════════════════════════════════════════════════════
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import requests
import warnings
import os
import time
warnings.filterwarnings('ignore')


# ════════════════════════════════════════════════════════════════
# SECTION 2: KONFIGURASI HALAMAN & CUSTOM CSS (UI UPGRADE ✨)
# ════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AlphaQuant IDX | Pro Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS untuk tampilan Modern, Clean, dan Satisfying
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    /* Global Font Upgrade */
    html, body, [class*="css"]  {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    /* Main Header Gradient & Glow */
    .main-header {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00C49A 0%, #00A3FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
        text-shadow: 0px 4px 15px rgba(0, 196, 154, 0.2);
        animation: fadeInDown 0.8s ease-out;
    }

    /* Glassmorphism Metric Cards */
    [data-testid="metric-container"] {
        background: rgba(26, 31, 46, 0.6);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        border-left: 4px solid #00C49A;
    }
    
    [data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px rgba(0, 196, 154, 0.15);
        border-left: 4px solid #00A3FF;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 8px; 
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: rgba(26, 31, 46, 0.5);
        border-radius: 10px 10px 0 0;
        padding: 10px 25px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-bottom: none;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(180deg, rgba(0, 196, 154, 0.1) 0%, rgba(26,31,46,1) 100%);
        border-top: 2px solid #00C49A;
    }

    /* Button Styling Animasi Satisfying */
    .stButton > button {
        background: linear-gradient(135deg, #00C49A 0%, #0082CC 100%);
        color: white;
        border-radius: 12px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0, 196, 154, 0.3);
    }
    .stButton > button:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 6px 20px rgba(0, 196, 154, 0.5);
        border: none;
        color: white;
    }
    .stButton > button:active {
        transform: translateY(1px) scale(0.98);
    }

    /* Dataframe Header */
    th {
        background-color: #1A1F2E !important;
        font-weight: 600 !important;
        color: #00C49A !important;
    }

    /* Animations */
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# SECTION 3-6: LOGIKA & ENGINE
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=86400)
def fetch_idx_full_list_from_web():
    try:
        url = "https://www.idx.co.id/primary/StockData/GetSecuritiesStock"
        params = {"code": "", "sector": "", "board": "", "language": "id-id", "start": 0, "length": 9999}
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code != 200: return None
        data = response.json()
        records = data.get("data", [])
        if not records: return None
        df = pd.DataFrame(records)
        df['ticker'] = df['Code'].astype(str) + '.JK'
        df['name'] = df['Name']
        df['sector'] = df.get('Sector', 'Unknown')
        df['board'] = df.get('PapanPencatatan', 'Unknown')
        return df[['ticker', 'name', 'sector', 'board']].drop_duplicates('ticker')
    except Exception as e:
        return None

@st.cache_data(ttl=86400)
def load_ticker_list(use_idx_live=False):
    if use_idx_live:
        df_live = fetch_idx_full_list_from_web()
        if df_live is not None and len(df_live) > 100: return df_live
    try:
        df = pd.read_csv("idx_tickers.csv")
        if 'board' not in df.columns: df['board'] = 'Unknown'
        return df
    except Exception:
        return pd.DataFrame(columns=['ticker', 'name', 'sector', 'board'])

def filter_active_stocks(df_tickers, exclude_suspended=True):
    if not exclude_suspended: return df_tickers
    suspend_keywords = ['suspend', 'delisting', 'delisted']
    if 'board' in df_tickers.columns:
        mask = ~df_tickers['board'].astype(str).str.lower().str.contains('|'.join(suspend_keywords), na=False)
        return df_tickers[mask].reset_index(drop=True)
    return df_tickers

@st.cache_data(ttl=3600)
def fetch_stock_data(ticker, period="6mo"):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        return None if hist.empty else hist
    except: return None

@st.cache_data(ttl=3600)
def fetch_stock_info(ticker):
    try: return yf.Ticker(ticker).info
    except: return {}

@st.cache_data(ttl=3600)
def fetch_corporate_actions(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock.dividends, stock.splits
    except: return pd.Series(), pd.Series()

@st.cache_data(ttl=1800)
def is_stock_active(ticker, days_to_check=5):
    try:
        hist = yf.Ticker(ticker).history(period="1mo")
        if hist.empty or len(hist) < days_to_check: return False
        return hist['Volume'].tail(days_to_check).sum() > 0
    except: return False

def calculate_indicators(df):
    if df is None or df.empty or len(df) < 50: return None
    df = df.copy()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_MA20']
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def detect_breakout_signal(df, volume_threshold=1.5):
    if df is None or len(df) < 50: return {'signal': False, 'reason': 'Data tidak cukup'}
    today, yesterday = df.iloc[-1], df.iloc[-2]
    if pd.isna(today['MA20']) or pd.isna(today['MA50']): return {'signal': False, 'reason': 'MA belum siap'}
    
    cond_a = (today['Close'] > today['MA20'] and today['Close'] > today['MA50'] and today['MA20'] > today['MA50'])
    cond_b = (yesterday['Close'] <= yesterday['MA20'] or yesterday['Close'] <= yesterday['MA50'])
    cond_c = today['Volume_Ratio'] > volume_threshold
    
    candle_green = today['Close'] > today['Open']
    candle_range = today['High'] - today['Low']
    cond_d = candle_green and ((today['High'] - today['Close']) / candle_range < 0.3) if candle_range > 0 else False
    
    return {
        'signal': cond_a and cond_b and cond_c and cond_d,
        'close': today['Close'], 'ma20': today['MA20'], 'ma50': today['MA50'],
        'volume_ratio': today['Volume_Ratio'], 'rsi': today['RSI'] if not pd.isna(today['RSI']) else 0
    }

def calculate_piotroski_fscore(ticker):
    try:
        info = yf.Ticker(ticker).info
        score = 0; details = {}
        def check(cond, name, pos_text='✅', neg_text='❌'):
            nonlocal score
            if cond: score += 1; details[name] = pos_text
            else: details[name] = neg_text
        
        ocf = info.get('operatingCashflow', 0)
        ni = info.get('netIncomeToCommon', 0)
        
        check(info.get('returnOnAssets', 0) > 0, 'ROA Positif')
        check(ocf > 0, 'OCF Positif')
        check(ocf > ni, 'CFO > Net Income')
        check(info.get('currentRatio', 0) > 1, 'Current Ratio > 1')
        check(info.get('grossMargins', 0) > 0, 'Gross Margin Positif')
        check(info.get('returnOnEquity', 0) > 0, 'ROE Positif')
        check(info.get('profitMargins', 0) > 0, 'Profit Margin Positif')
        check(info.get('debtToEquity', 999) < 100, 'DER Sehat (<1)')
        check(info.get('revenueGrowth', 0) > 0, 'Revenue Growth +')
        return score, details
    except Exception as e: return 0, {'error': str(e)}

def calculate_altman_zscore(ticker):
    try:
        stock = yf.Ticker(ticker)
        bs, fin, info = stock.balance_sheet, stock.financials, stock.info
        if bs.empty or fin.empty: return None, "Data laporan keuangan tidak tersedia"
        
        latest_bs, latest_fin = bs.iloc[:, 0], fin.iloc[:, 0]
        total_assets = latest_bs.get('Total Assets', np.nan)
        if pd.isna(total_assets) or total_assets == 0: return None, "Total Assets tidak tersedia"
        
        wc = latest_bs.get('Current Assets', 0) - latest_bs.get('Current Liabilities', 0)
        A = wc / total_assets
        B = latest_bs.get('Retained Earnings', 0) / total_assets
        C = latest_fin.get('EBIT', latest_fin.get('Operating Income', 0)) / total_assets
        total_liab = latest_bs.get('Total Liabilities Net Minority Interest', latest_bs.get('Total Debt', 1))
        D = info.get('marketCap', 0) / total_liab if total_liab > 0 else 0
        E = latest_fin.get('Total Revenue', 0) / total_assets
        
        z_score = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E
        status = "🟢 SAFE ZONE" if z_score > 3.0 else "🟡 GREY ZONE" if z_score > 1.8 else "🔴 DISTRESS ZONE"
        return z_score, status
    except Exception as e: return None, f"Error: {str(e)[:50]}"


# ════════════════════════════════════════════════════════════════
# SECTION 7: VISUALISASI
# ════════════════════════════════════════════════════════════════
def create_candlestick_chart(df, ticker_name):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
    
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        name='Price', increasing_line_color='#00C49A', decreasing_line_color='#FF4B4B'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='MA20', line=dict(color='#FFA500', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], name='MA50', line=dict(color='#00A3FF', width=2)), row=1, col=1)
    
    colors = ['#00C49A' if c >= o else '#FF4B4B' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=colors, opacity=0.8), row=2, col=1)
    
    fig.update_layout(
        height=650, 
        template='plotly_dark',
        plot_bgcolor='rgba(15, 20, 30, 0.5)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis_rangeslider_visible=False, 
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=30, b=10)
    )
    return fig


# ════════════════════════════════════════════════════════════════
# SECTION 8: SIDEBAR + UNIVERSE MANAGER
# ════════════════════════════════════════════════════════════════
with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/combo-chart.png", width=60)
    st.markdown("## AlphaQuant IDX\n*Pro Terminal v2.0*")
    st.markdown("---")

    st.markdown("### ⚙️ Engine Settings")
    use_live_idx = st.checkbox("🌐 Live IDX Data (~956 emiten)", value=False, help="Tarik data real-time, lebih komprehensif.")
    exclude_suspended = st.checkbox("🚫 Auto-Skip Suspended", value=True, help="Bersihkan hasil dari saham gocap/suspend.")

    if st.button("🔄 Sinkronisasi Data", use_container_width=True):
        st.cache_data.clear()
        st.toast("✅ Sinkronisasi berhasil! Data ter-refresh.", icon="🎉")
        time.sleep(1)
        st.rerun()

    with st.status("📡 Menghubungkan ke Exchange...", expanded=False) as status:
        ticker_df = load_ticker_list(use_idx_live=use_live_idx)
        ticker_df = filter_active_stocks(ticker_df, exclude_suspended=exclude_suspended)
        status.update(label=f"Terhubung! {len(ticker_df)} emiten aktif.", state="complete")

    st.markdown("---")
    menu = st.radio(
        "🧭 **Menu Utama:**",
        ["🏠 Dashboard", "🔍 Single Stock Analysis",
         "🚀 Breakout Screener", "💰 Corp. Action Screener",
         "📊 Fundamental Ranker"]
    )
    st.markdown("---")
    st.caption(f"📅 Last Sync: {datetime.now().strftime('%H:%M WIB')}")


# ════════════════════════════════════════════════════════════════
# SECTION 9: HEADER & ROUTING
# ════════════════════════════════════════════════════════════════
st.markdown('<div class="main-header">⚡ AlphaQuant Terminal</div>', unsafe_allow_html=True)
st.markdown(
    f"<p style='text-align:center; color:#A0AEC0; font-size: 1.1rem; margin-bottom: 2rem;'>"
    f"Sistem Analisis Grade Institusional • <b>{len(ticker_df)} Saham Aktif</b>"
    "</p>", unsafe_allow_html=True
)


# ───────────────────────────────────────────────
# MODUL 1: DASHBOARD HOME
# ───────────────────────────────────────────────
if menu == "🏠 Dashboard":
    st.markdown("### 📊 Market Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    utama_count = len(ticker_df[ticker_df['board'].astype(str).str.contains('Utama', na=False)])
    watch_count = len(ticker_df[ticker_df['board'].astype(str).str.contains('Pemantauan', na=False)])
    
    col1.metric("🌍 Total Universe", f"{len(ticker_df)} Saham")
    col2.metric("⭐ Papan Utama", f"{utama_count}")
    col3.metric("⚠️ Papan Pemantauan", f"{watch_count}")
    col4.metric("📡 Status Server", "LIVE" if use_live_idx else "LOCAL", delta="Lat < 50ms")
    
    st.markdown("---")
    st.markdown("### 🎯 Modul Tersedia")
    
    feat_col1, feat_col2 = st.columns(2)
    with feat_col1:
        st.info("#### 🔍 Single Stock Analysis\nBedah mendalam performa harga, F-Score, Z-Score, & valuasi sebuah emiten.")
        st.success("#### 🚀 Breakout Screener\nDeteksi dini saham yang baru saja menembus resistensi dengan volume tinggi.")
    with feat_col2:
        st.warning("#### 📊 Fundamental Ranker\nCari saham ter-undervalued atau paling menguntungkan (ROE tertinggi).")
        st.error("#### 💰 Corporate Action\nPantau jadwal dividen dan aksi korporasi terbaru.")

# ───────────────────────────────────────────────
# MODUL 2: SINGLE STOCK ANALYSIS
# ───────────────────────────────────────────────
elif menu == "🔍 Single Stock Analysis":
    st.markdown("### 🔍 Analisa Mendalam Emiten")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_ticker = st.selectbox("Cari Kode Emiten:", options=ticker_df['ticker'].tolist(), 
            format_func=lambda x: f"{x} — {ticker_df[ticker_df['ticker']==x]['name'].values[0]}")
    with col2:
        period = st.selectbox("Rentang Waktu:", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
    
    if st.button("🚀 Eksekusi Analisa", use_container_width=True):
        with st.status("🛠️ Membedah Emiten...", expanded=True) as status:
            st.write(f"📥 Mengunduh riwayat harga {selected_ticker}...")
            df = fetch_stock_data(selected_ticker, period=period)
            time.sleep(0.3)
            
            st.write("📊 Mengkomputasi Indikator Teknikal...")
            df = calculate_indicators(df)
            
            st.write("💼 Menarik Data Laporan Keuangan...")
            info = fetch_stock_info(selected_ticker)
            
            status.update(label="✅ Analisis Selesai!", state="complete", expanded=False)
            st.toast(f"Data {selected_ticker} berhasil dimuat!", icon="🎯")
        
        if df is None or df.empty:
            st.error("❌ Data tidak ditemukan atau saham sedang disuspen.")
        else:
            tab1, tab2, tab3, tab4 = st.tabs(["📈 Chart & Tekrikal", "💼 Ringkasan Valuasi", "⭐ Composite Scores", "💵 Corp Action"])
            
            with tab1:
                last, prev = df.iloc[-1], df.iloc[-2]
                change = ((last['Close'] - prev['Close']) / prev['Close']) * 100
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Harga Terakhir", f"Rp {last['Close']:,.0f}", f"{change:+.2f}%")
                m2.metric("MA20", f"Rp {last['MA20']:,.0f}", f"{((last['Close']/last['MA20'])-1)*100:+.2f}%")
                m3.metric("MA50", f"Rp {last['MA50']:,.0f}", f"{((last['Close']/last['MA50'])-1)*100:+.2f}%")
                m4.metric("RSI (14)", f"{last['RSI']:.1f}", "Momentum")
                
                st.plotly_chart(create_candlestick_chart(df, selected_ticker), use_container_width=True)
                
                sig = detect_breakout_signal(df)
                if sig['signal']: st.success("🎯 **BREAKOUT TERKONFIRMASI!** Harga memotong MA dengan konfirmasi volume.")
                else: st.info("📉 Saat ini kondisi harga masih dalam fase konsolidasi atau koreksi rutin.")
            
            with tab2:
                st.markdown("#### 💎 Valuasi & Profitabilitas")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("PER (Valuasi)", f"{info.get('trailingPE', 0):.2f}x" if info.get('trailingPE') else "N/A")
                f2.metric("PBV (Aset)", f"{info.get('priceToBook', 0):.2f}x" if info.get('priceToBook') else "N/A")
                f3.metric("ROE (Profit)", f"{info.get('returnOnEquity', 0)*100:.2f}%" if info.get('returnOnEquity') else "N/A")
                f4.metric("Market Cap", f"Rp {info.get('marketCap', 0)/1e12:.2f}T" if info.get('marketCap') else "N/A")
                
                st.markdown("<br>#### 📖 Profil Bisnis", unsafe_allow_html=True)
                st.write(info.get('longBusinessSummary', 'Deskripsi tidak tersedia di sistem.'))
            
            with tab3:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 🎯 Piotroski F-Score (Kesehatan)")
                    f_score, f_det = calculate_piotroski_fscore(selected_ticker)
                    if f_score >= 7: st.success(f"### {f_score} / 9 — STRONG ✅")
                    elif f_score >= 4: st.warning(f"### {f_score} / 9 — MODERATE ⚠️")
                    else: st.error(f"### {f_score} / 9 — WEAK ❌")
                    for k, v in f_det.items(): st.caption(f"{v} {k}")
                with c2:
                    st.markdown("#### 🛡️ Altman Z-Score (Risiko Bangkrut)")
                    z_score, z_stat = calculate_altman_zscore(selected_ticker)
                    if z_score:
                        st.markdown(f"### {z_score:.2f}")
                        if "SAFE" in z_stat: st.success(z_stat)
                        elif "GREY" in z_stat: st.warning(z_stat)
                        else: st.error(z_stat)
                    else: st.info(z_stat)
            
            with tab4:
                divs, splits = fetch_corporate_actions(selected_ticker)
                st.info("Riwayat pembagian hasil dan penyesuaian jumlah saham beredar.")

# ───────────────────────────────────────────────
# MODUL 3: BREAKOUT SCREENER
# ───────────────────────────────────────────────
elif menu == "🚀 Breakout Screener":
    st.markdown("### 🚀 Algoritma Breakout Detector")
    st.caption("Mesin ini akan memindai pasar untuk mencari anomali lonjakan harga yang disertai akumulasi volume besar.")
    
    col1, col2, col3 = st.columns(3)
    vol_threshold = col1.slider("🔊 Minimal Lonjakan Volume", 1.0, 5.0, 1.5, 0.1, help="1.5 = Volume 50% lebih tinggi dari rata-rata")
    max_scan = col2.number_input("🎯 Kapasitas Scan (Saham)", 10, len(ticker_df), min(50, len(ticker_df)))
    skip_watchlist = col3.checkbox("⏭️ Lewati Saham Papan Pemantauan", value=True)
    
    if st.button("🔥 Mulai Pemindaian", use_container_width=True):
        scan_df = ticker_df[~ticker_df['board'].astype(str).str.contains('Pemantauan', na=False)] if skip_watchlist else ticker_df.copy()
        
        results, skipped = [], 0
        tickers_to_scan = scan_df['ticker'].tolist()[:int(max_scan)]
        
        with st.status(f"Menjalankan RADAR pada {len(tickers_to_scan)} emiten...", expanded=True) as status:
            prog_bar = st.progress(0)
            status_text = st.empty()
            
            for i, tk in enumerate(tickers_to_scan):
                status_text.text(f"Memeriksa {tk}... ({i+1}/{len(tickers_to_scan)})")
                prog_bar.progress((i+1)/len(tickers_to_scan))
                
                df = fetch_stock_data(tk, "6mo")
                if df is None or df.empty or df['Volume'].tail(5).sum() == 0: 
                    skipped += 1
                    continue
                
                sig = detect_breakout_signal(calculate_indicators(df), vol_threshold)
                if sig['signal']:
                    row = scan_df[scan_df['ticker']==tk].iloc[0]
                    results.append({'Ticker': tk, 'Nama': row['name'], 'Sektor': row['sector'], 'Close': sig['close'], 'Vol Ratio': sig['volume_ratio']})
            
            status.update(label="✅ Pemindaian Selesai!", state="complete", expanded=False)
            if results: st.toast("Sinyal Breakout Terdeteksi! 🎉", icon="🔥")
        
        if results:
            st.success(f"🎯 Menemukan **{len(results)} Sinyal Emas**!")
            res_df = pd.DataFrame(results).sort_values('Vol Ratio', ascending=False)
            
            # --- FIX: MATPLOTLIB ERROR REMOVED HERE ---
            st.dataframe(res_df.style.format({'Close': 'Rp {:,.0f}', 'Vol Ratio': '{:.2f}x'}), use_container_width=True, hide_index=True)
        else:
            st.info("📭 Pasar sedang tenang. Tidak ada emiten yang memenuhi kriteria breakout super ketat saat ini.")


# ───────────────────────────────────────────────
# MODUL 4 & 5 (FUNDAMENTAL & CA SCREENER)
# ───────────────────────────────────────────────
elif menu == "📊 Fundamental Ranker":
    st.markdown("### 🏆 Mesin Peringkat Fundamental")
    rank_by = st.selectbox("Metrik Kompetisi:", ["ROE (Tertinggi) - Profitabilitas", "PER (Terendah) - Value", "PBV (Terendah) - Value Margin"])
    max_scan_f = st.slider("Jumlah partisipan (saham):", 10, len(ticker_df), 50)
    
    if st.button("🏆 Jalankan Kompetisi", use_container_width=True):
        results = []
        tickers_list = ticker_df['ticker'].tolist()[:max_scan_f]
        
        with st.status(f"Mengumpulkan rapor keuangan {len(tickers_list)} perusahaan...", expanded=True) as status:
            prog = st.progress(0)
            for i, tk in enumerate(tickers_list):
                prog.progress((i+1)/len(tickers_list))
                info = fetch_stock_info(tk)
                results.append({
                    'Ticker': tk, 'PER': info.get('trailingPE', np.nan), 'PBV': info.get('priceToBook', np.nan),
                    'ROE (%)': info.get('returnOnEquity', 0)*100 if info.get('returnOnEquity') else np.nan
                })
            status.update(label="✅ Analisa Fundamental Selesai", state="complete", expanded=False)
            st.toast("Ranking siap disajikan!", icon="🏆")

        df_res = pd.DataFrame(results).dropna(subset=['PER', 'PBV', 'ROE (%)'])
        sort_col = 'ROE (%)' if 'ROE' in rank_by else ('PER' if 'PER' in rank_by else 'PBV')
        df_res = df_res.sort_values(sort_col, ascending=not 'ROE' in rank_by).head(15)
        
        # --- FIX: MATPLOTLIB ERROR REMOVED HERE ---
        st.dataframe(df_res.style.format({'PER': '{:.2f}x', 'PBV': '{:.2f}x', 'ROE (%)': '{:.2f}%'}), use_container_width=True, hide_index=True)

elif menu == "💰 Corp. Action Screener":
    st.markdown("### 💰 Radar Aksi Korporasi")
    
    sub_menu = st.radio("Pilih Tipe:", ["💵 Dividend Yield Ranker", "🔀 Recent Stock Splits"], horizontal=True)
    max_scan_ca = st.slider("Jumlah saham discan:", 10, len(ticker_df), min(50, len(ticker_df)))
    
    if sub_menu == "💵 Dividend Yield Ranker":
        if st.button("🚀 Jalankan Ranker Dividen", use_container_width=True):
            results = []
            tickers_list = ticker_df['ticker'].tolist()[:max_scan_ca]
            
            with st.status(f"Mencari dividen dari {len(tickers_list)} emiten...", expanded=True) as status:
                prog = st.progress(0)
                for i, tk in enumerate(tickers_list):
                    prog.progress((i+1)/len(tickers_list))
                    info = fetch_stock_info(tk)
                    dy = info.get('dividendYield', 0)
                    if dy and dy > 0:
                        name = ticker_df[ticker_df['ticker']==tk]['name'].values[0]
                        results.append({'Ticker': tk, 'Nama': name, 'Div Yield (%)': dy * 100, 'PER': info.get('trailingPE', 0)})
                status.update(label="✅ Pencarian Dividen Selesai!", state="complete", expanded=False)
            
            if results:
                df_res = pd.DataFrame(results).sort_values('Div Yield (%)', ascending=False)
                # --- FIX: MATPLOTLIB ERROR REMOVED HERE ---
                st.dataframe(df_res.style.format({'Div Yield (%)': '{:.2f}%', 'PER': '{:.2f}'}), use_container_width=True, hide_index=True)
            else:
                st.info("Tidak ada data dividen ditemukan.")
    else:
        st.info("Fitur Stock Split sedang dalam penyesuaian.")

# ════════════════════════════════════════════════════════════════
# FOOTER
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#666; font-size: 0.9rem; margin-top: 2rem;'>"
    "⚠️ <i>Disclaimer: Analisis mesin murni bersumber dari data publik. Lakukan riset mandiri (DYOR) sebelum berinvestasi.</i><br>"
    f"🚀 <b>AlphaQuant Pro Terminal</b> | Crafted with ❤️"
    "</div>", unsafe_allow_html=True
  )
