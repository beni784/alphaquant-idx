"""
═══════════════════════════════════════════════════════════════════
  ALPHAQUANT IDX v2.0 - Full Universe + Auto-Updater
  Update: Support 956+ emiten dengan auto-refresh dari IDX
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
warnings.filterwarnings('ignore')


# ════════════════════════════════════════════════════════════════
# SECTION 2: KONFIGURASI HALAMAN STREAMLIT
# ════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AlphaQuant IDX | Institutional Stock Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00C49A 0%, #00A3FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background-color: #1A1F2E;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #00C49A;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1A1F2E;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# SECTION 3: SMART AUTO-UPDATER (FITUR BARU v2.0)
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=86400)  # Cache 24 jam
def fetch_idx_full_list_from_web():
    """
    🔥 FITUR BARU: Auto-fetch daftar SEMUA saham IDX dari endpoint resmi.
    Endpoint ini dipakai web idx.co.id sendiri untuk load daftar saham.
    
    Returns: DataFrame dengan kolom [ticker, name, sector, board]
    """
    try:
        # Endpoint IDX (JSON API tersembunyi yang dipakai web mereka)
        url = "https://www.idx.co.id/primary/StockData/GetSecuritiesStock"
        params = {
            "code": "",
            "sector": "",
            "board": "",
            "language": "id-id",
            "start": 0,
            "length": 9999  # Ambil semua sekaligus
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AlphaQuant/2.0",
            "Accept": "application/json"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        records = data.get("data", [])
        
        if not records:
            return None
        
        # Parse ke DataFrame
        df = pd.DataFrame(records)
        
        # Standarisasi kolom
        df['ticker'] = df['Code'].astype(str) + '.JK'
        df['name'] = df['Name']
        df['sector'] = df.get('Sector', 'Unknown')
        df['board'] = df.get('PapanPencatatan', 'Unknown')
        
        # FILTER PENTING: Buang saham yang sudah delisting/suspend permanen
        # Saham di papan "Pemantauan Khusus" tetap diperdagangkan (warning saja)
        # Saham delisting akan otomatis tidak ada di response API ini
        
        return df[['ticker', 'name', 'sector', 'board']].drop_duplicates('ticker')
    
    except Exception as e:
        st.warning(f"⚠️ Gagal auto-fetch dari IDX: {str(e)[:80]}. Pakai daftar lokal.")
        return None


@st.cache_data(ttl=86400)
def load_ticker_list(use_idx_live=False):
    """
    Load daftar saham dengan strategi DUAL-SOURCE:
    1. Coba fetch live dari IDX (jika use_idx_live=True)
    2. Fallback ke CSV lokal
    """
    if use_idx_live:
        df_live = fetch_idx_full_list_from_web()
        if df_live is not None and len(df_live) > 100:
            return df_live
    
    # Fallback: load dari CSV lokal
    try:
        df = pd.read_csv("idx_tickers.csv")
        if 'board' not in df.columns:
            df['board'] = 'Unknown'
        return df
    except Exception as e:
        st.error(f"Gagal memuat daftar saham: {e}")
        return pd.DataFrame(columns=['ticker', 'name', 'sector', 'board'])


def filter_active_stocks(df_tickers, exclude_suspended=True):
    """
    Filter saham yang aktif diperdagangkan.
    Default: Buang yang ada di papan suspensi/delisting indicator.
    
    Note: Papan "Pemantauan Khusus" TETAP diperdagangkan, hanya warning
    bahwa fundamental perusahaan kurang sehat. Tidak di-exclude default.
    """
    if not exclude_suspended:
        return df_tickers
    
    # Hanya exclude jika ada flag eksplisit "Suspend" atau "Delisting"
    suspend_keywords = ['suspend', 'delisting', 'delisted']
    
    if 'board' in df_tickers.columns:
        mask = ~df_tickers['board'].astype(str).str.lower().str.contains(
            '|'.join(suspend_keywords), na=False
        )
        return df_tickers[mask].reset_index(drop=True)
    
    return df_tickers


# ════════════════════════════════════════════════════════════════
# SECTION 4: DATA FETCHER (existing, tidak berubah)
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def fetch_stock_data(ticker, period="6mo"):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            return None
        return hist
    except Exception as e:
        return None


@st.cache_data(ttl=3600)
def fetch_stock_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock.info
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def fetch_corporate_actions(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock.dividends, stock.splits
    except Exception:
        return pd.Series(), pd.Series()


@st.cache_data(ttl=1800)
def is_stock_active(ticker, days_to_check=5):
    """
    🔥 FITUR BARU: Cek apakah saham masih aktif diperdagangkan.
    Cara: Cek volume 5 hari terakhir. Jika semua 0 → kemungkinan suspend.
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")
        if hist.empty or len(hist) < days_to_check:
            return False
        recent_volume = hist['Volume'].tail(days_to_check).sum()
        return recent_volume > 0
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════
# SECTION 5: TECHNICAL ENGINE
# ════════════════════════════════════════════════════════════════

def calculate_indicators(df):
    if df is None or df.empty or len(df) < 50:
        return None
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
    if df is None or len(df) < 50:
        return {'signal': False, 'reason': 'Data tidak cukup'}
    
    today = df.iloc[-1]
    yesterday = df.iloc[-2]
    
    if pd.isna(today['MA20']) or pd.isna(today['MA50']):
        return {'signal': False, 'reason': 'MA belum siap'}
    
    cond_a = (today['Close'] > today['MA20'] and 
              today['Close'] > today['MA50'] and
              today['MA20'] > today['MA50'])
    cond_b = (yesterday['Close'] <= yesterday['MA20'] or 
              yesterday['Close'] <= yesterday['MA50'])
    cond_c = today['Volume_Ratio'] > volume_threshold
    
    candle_green = today['Close'] > today['Open']
    candle_range = today['High'] - today['Low']
    if candle_range > 0:
        close_position = (today['High'] - today['Close']) / candle_range
        cond_d = candle_green and close_position < 0.3
    else:
        cond_d = False
    
    signal = cond_a and cond_b and cond_c and cond_d
    
    return {
        'signal': signal,
        'close': today['Close'],
        'ma20': today['MA20'],
        'ma50': today['MA50'],
        'volume_ratio': today['Volume_Ratio'],
        'rsi': today['RSI'] if not pd.isna(today['RSI']) else 0,
        'cond_a_trend': cond_a,
        'cond_b_fresh': cond_b,
        'cond_c_volume': cond_c,
        'cond_d_candle': cond_d
    }


# ════════════════════════════════════════════════════════════════
# SECTION 6: FUNDAMENTAL ENGINE
# ════════════════════════════════════════════════════════════════

def calculate_piotroski_fscore(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        score = 0
        details = {}
        
        roa = info.get('returnOnAssets', 0)
        if roa and roa > 0: score += 1; details['ROA Positif'] = '✅'
        else: details['ROA Positif'] = '❌'
        
        ocf = info.get('operatingCashflow', 0)
        if ocf and ocf > 0: score += 1; details['OCF Positif'] = '✅'
        else: details['OCF Positif'] = '❌'
        
        ni = info.get('netIncomeToCommon', 0)
        if ocf and ni and ocf > ni: score += 1; details['CFO > Net Income'] = '✅'
        else: details['CFO > Net Income'] = '❌'
        
        cr = info.get('currentRatio', 0)
        if cr and cr > 1: score += 1; details['Current Ratio > 1'] = '✅'
        else: details['Current Ratio > 1'] = '❌'
        
        gm = info.get('grossMargins', 0)
        if gm and gm > 0: score += 1; details['Gross Margin Positif'] = '✅'
        else: details['Gross Margin Positif'] = '❌'
        
        roe = info.get('returnOnEquity', 0)
        if roe and roe > 0: score += 1; details['ROE Positif'] = '✅'
        else: details['ROE Positif'] = '❌'
        
        pm = info.get('profitMargins', 0)
        if pm and pm > 0: score += 1; details['Profit Margin Positif'] = '✅'
        else: details['Profit Margin Positif'] = '❌'
        
        de = info.get('debtToEquity', 999)
        if de and de < 100: score += 1; details['DER Sehat (<1)'] = '✅'
        else: details['DER Sehat (<1)'] = '❌'
        
        rg = info.get('revenueGrowth', 0)
        if rg and rg > 0: score += 1; details['Revenue Growth +'] = '✅'
        else: details['Revenue Growth +'] = '❌'
        
        return score, details
    except Exception as e:
        return 0, {'error': str(e)}


def calculate_altman_zscore(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        bs = stock.balance_sheet
        fin = stock.financials
        
        if bs.empty or fin.empty:
            return None, "Data laporan keuangan tidak tersedia"
        
        latest_bs = bs.iloc[:, 0]
        latest_fin = fin.iloc[:, 0]
        
        total_assets = latest_bs.get('Total Assets', np.nan)
        if pd.isna(total_assets) or total_assets == 0:
            return None, "Total Assets tidak tersedia"
        
        current_assets = latest_bs.get('Current Assets', 0)
        current_liab = latest_bs.get('Current Liabilities', 0)
        wc = current_assets - current_liab
        A = wc / total_assets
        
        re = latest_bs.get('Retained Earnings', 0)
        B = re / total_assets
        
        ebit = latest_fin.get('EBIT', latest_fin.get('Operating Income', 0))
        C = ebit / total_assets
        
        mcap = info.get('marketCap', 0)
        total_liab = latest_bs.get('Total Liabilities Net Minority Interest',
                                    latest_bs.get('Total Debt', 1))
        D = mcap / total_liab if total_liab > 0 else 0
        
        revenue = latest_fin.get('Total Revenue', 0)
        E = revenue / total_assets
        
        z_score = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E
        
        if z_score > 3.0: status = "🟢 SAFE ZONE"
        elif z_score > 1.8: status = "🟡 GREY ZONE"
        else: status = "🔴 DISTRESS ZONE"
        
        return z_score, status
    except Exception as e:
        return None, f"Error: {str(e)[:50]}"


# ════════════════════════════════════════════════════════════════
# SECTION 7: VISUALISASI
# ════════════════════════════════════════════════════════════════

def create_candlestick_chart(df, ticker_name):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=[0.7, 0.3],
        subplot_titles=(f'{ticker_name} - Price Chart', 'Volume')
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name='Price',
        increasing_line_color='#00C49A', decreasing_line_color='#FF4B4B'
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MA20'], name='MA20',
        line=dict(color='#FFA500', width=1.5)
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MA50'], name='MA50',
        line=dict(color='#00A3FF', width=1.5)
    ), row=1, col=1)
    colors = ['#00C49A' if c >= o else '#FF4B4B'
              for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'], name='Volume', marker_color=colors
    ), row=2, col=1)
    fig.update_layout(
        height=600, template='plotly_dark',
        xaxis_rangeslider_visible=False, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    return fig


# ════════════════════════════════════════════════════════════════
# SECTION 8: SIDEBAR + UNIVERSE MANAGER (UPDATED)
# ════════════════════════════════════════════════════════════════

st.sidebar.markdown("# 📈 AlphaQuant IDX")
st.sidebar.markdown("*Institutional Stock Analyzer v2.0*")
st.sidebar.markdown("---")

# 🔥 FITUR BARU: Universe Manager
st.sidebar.markdown("### 🌐 Universe Manager")

use_live_idx = st.sidebar.checkbox(
    "🔴 Live IDX Data (~956 emiten)",
    value=False,
    help="Auto-fetch daftar terbaru dari IDX. Lebih lama tapi lengkap."
)

exclude_suspended = st.sidebar.checkbox(
    "🚫 Exclude Suspended Stocks",
    value=True,
    help="Auto-skip saham yang volume-nya 0 selama 5 hari (proxy suspend)."
)

if st.sidebar.button("🔄 Refresh Daftar Saham", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# Load ticker list
with st.spinner("Loading universe..."):
    ticker_df = load_ticker_list(use_idx_live=use_live_idx)
    ticker_df = filter_active_stocks(ticker_df, exclude_suspended=exclude_suspended)

st.sidebar.success(f"✅ Loaded **{len(ticker_df)}** saham aktif")

st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "🧭 **Navigasi Modul:**",
    ["🏠 Dashboard", "🔍 Single Stock Analysis",
     "🚀 Breakout Screener", "💰 Corporate Action Screener",
     "📊 Fundamental Ranker"]
)

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 **Pro Tip:**\n\n"
    "Aktifkan 'Live IDX Data' untuk akses ~956 emiten. "
    "Mode default pakai 250 saham paling likuid (lebih cepat)."
)
st.sidebar.markdown("---")
st.sidebar.caption(f"📅 {datetime.now().strftime('%d %B %Y, %H:%M')} WIB")
st.sidebar.caption("⚡ Powered by AlphaQuant Engine")


# ════════════════════════════════════════════════════════════════
# SECTION 9: HEADER & ROUTING
# ════════════════════════════════════════════════════════════════

st.markdown('<div class="main-header">📊 AlphaQuant IDX Terminal</div>',
            unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center; color:#888;'>"
    "Institutional-Grade Analysis untuk Saham Indonesia"
    f" • <b>{len(ticker_df)} emiten aktif</b>"
    "</p>", unsafe_allow_html=True
)
st.markdown("---")


# ───────────────────────────────────────────────
# MODUL 1: DASHBOARD HOME
# ───────────────────────────────────────────────
if menu == "🏠 Dashboard":
    st.subheader("Selamat Datang di AlphaQuant IDX")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Universe", f"{len(ticker_df)} Saham")
    with col2:
        utama_count = len(ticker_df[ticker_df['board'].astype(str).str.contains('Utama', na=False)])
        st.metric("⭐ Papan Utama", f"{utama_count}")
    with col3:
        watch_count = len(ticker_df[ticker_df['board'].astype(str).str.contains('Pemantauan', na=False)])
        st.metric("⚠️ Pemantauan Khusus", f"{watch_count}")
    with col4:
        st.metric("🔄 Mode", "Live" if use_live_idx else "Local")
    
    st.markdown("### 🎯 Fitur Platform v2.0")
    
    feat_col1, feat_col2 = st.columns(2)
    with feat_col1:
        st.markdown("""
        #### 🌐 Universe Penuh BEI
        - Auto-fetch ~956 emiten dari IDX
        - Filter saham suspend otomatis
        - Klasifikasi papan pencatatan
        - Refresh on-demand
        
        #### 🔍 Single Stock Analysis
        - Chart candlestick interaktif
        - Indikator: MA20, MA50, MA200, RSI
        - Piotroski F-Score & Altman Z-Score
        """)
    with feat_col2:
        st.markdown("""
        #### 🚀 Breakout Screener
        - 4-kondisi multi-filter
        - Anti false-signal
        - Volume surge confirmation
        
        #### 📊 Fundamental Ranker
        - Top stocks by ROE
        - Lowest PER/PBV
        - Highest dividend yield
        """)
    
    # Distribusi saham per papan
    st.markdown("### 📊 Distribusi Saham per Papan Pencatatan")
    if 'board' in ticker_df.columns:
        board_counts = ticker_df['board'].value_counts()
        fig_pie = go.Figure(data=[go.Pie(
            labels=board_counts.index,
            values=board_counts.values,
            hole=0.4,
            marker=dict(colors=['#00C49A', '#FFA500', '#00A3FF', '#FF4B4B', '#9B59B6'])
        )])
        fig_pie.update_layout(template='plotly_dark', height=400)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    st.info("👈 Pilih modul dari sidebar untuk mulai analisa.")


# ───────────────────────────────────────────────
# MODUL 2: SINGLE STOCK ANALYSIS
# ───────────────────────────────────────────────
elif menu == "🔍 Single Stock Analysis":
    st.subheader("🔍 Analisa Saham Individual")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_ticker = st.selectbox(
            "Pilih Saham:",
            options=ticker_df['ticker'].tolist(),
            format_func=lambda x: f"{x} - {ticker_df[ticker_df['ticker']==x]['name'].values[0]}"
        )
    with col2:
        period = st.selectbox("Periode:", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
    
    if st.button("🚀 Analisa Sekarang", use_container_width=True):
        with st.spinner(f"Mengambil data {selected_ticker}..."):
            df = fetch_stock_data(selected_ticker, period=period)
            info = fetch_stock_info(selected_ticker)
            df = calculate_indicators(df)
        
        if df is None or df.empty:
            st.error("❌ Data tidak tersedia. Saham mungkin suspend atau ticker invalid.")
        else:
            tab1, tab2, tab3, tab4 = st.tabs([
                "📈 Chart", "💼 Fundamental", "⭐ Scores", "💵 Corp. Action"
            ])
            
            with tab1:
                last = df.iloc[-1]
                prev = df.iloc[-2]
                change = ((last['Close'] - prev['Close']) / prev['Close']) * 100
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("💵 Last Price", f"Rp {last['Close']:,.0f}", f"{change:+.2f}%")
                m2.metric("📊 MA20", f"Rp {last['MA20']:,.0f}",
                          f"{((last['Close']/last['MA20'])-1)*100:+.2f}%")
                m3.metric("📈 MA50", f"Rp {last['MA50']:,.0f}",
                          f"{((last['Close']/last['MA50'])-1)*100:+.2f}%")
                m4.metric("📦 Vol Ratio", f"{last['Volume_Ratio']:.2f}x", "vs 20D avg")
                
                fig = create_candlestick_chart(df, selected_ticker)
                st.plotly_chart(fig, use_container_width=True)
                
                signal = detect_breakout_signal(df)
                if signal['signal']:
                    st.success("🚀 **BREAKOUT SIGNAL TERDETEKSI!** Semua 4 kondisi terpenuhi.")
                else:
                    st.info("📊 Tidak ada sinyal breakout aktif saat ini.")
            
            with tab2:
                st.markdown("### 💼 Metrik Fundamental")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("PER", f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else "N/A")
                f2.metric("PBV", f"{info.get('priceToBook', 0):.2f}" if info.get('priceToBook') else "N/A")
                f3.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.2f}%" if info.get('returnOnEquity') else "N/A")
                f4.metric("ROA", f"{info.get('returnOnAssets', 0)*100:.2f}%" if info.get('returnOnAssets') else "N/A")
                
                f5, f6, f7, f8 = st.columns(4)
                f5.metric("DER", f"{info.get('debtToEquity', 0):.2f}" if info.get('debtToEquity') else "N/A")
                f6.metric("Profit Margin", f"{info.get('profitMargins', 0)*100:.2f}%" if info.get('profitMargins') else "N/A")
                f7.metric("Div Yield", f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "N/A")
                f8.metric("Market Cap", f"Rp {info.get('marketCap', 0)/1e12:.2f}T" if info.get('marketCap') else "N/A")
                
                st.markdown("#### 📋 Profil Perusahaan")
                st.write(f"**Nama:** {info.get('longName', 'N/A')}")
                st.write(f"**Sektor:** {info.get('sector', 'N/A')}")
                st.write(f"**Industri:** {info.get('industry', 'N/A')}")
                with st.expander("📖 Deskripsi Bisnis"):
                    st.write(info.get('longBusinessSummary', 'Tidak tersedia.'))
            
            with tab3:
                st.markdown("### ⭐ Institutional Composite Scores")
                col_p, col_a = st.columns(2)
                
                with col_p:
                    st.markdown("#### 🎯 Piotroski F-Score")
                    f_score, f_details = calculate_piotroski_fscore(selected_ticker)
                    if f_score >= 7: st.success(f"## {f_score} / 9 — STRONG ✅")
                    elif f_score >= 4: st.warning(f"## {f_score} / 9 — MODERATE ⚠️")
                    else: st.error(f"## {f_score} / 9 — WEAK ❌")
                    
                    st.markdown("**Detail Kriteria:**")
                    for k, v in f_details.items():
                        st.write(f"{v} {k}")
                
                with col_a:
                    st.markdown("#### 🛡️ Altman Z-Score")
                    z_score, z_status = calculate_altman_zscore(selected_ticker)
                    if z_score is not None:
                        st.markdown(f"## {z_score:.2f}")
                        st.markdown(f"### {z_status}")
                        st.markdown("""
                        **Interpretasi:**
                        - 🟢 Z > 3.0: Safe
                        - 🟡 1.8 < Z < 3.0: Grey Zone
                        - 🔴 Z < 1.8: Distress
                        """)
                    else:
                        st.warning(z_status)
            
            with tab4:
                st.markdown("### 💵 Riwayat Aksi Korporasi")
                divs, splits = fetch_corporate_actions(selected_ticker)
                ca_col1, ca_col2 = st.columns(2)
                with ca_col1:
                    st.markdown("#### 💰 Riwayat Dividen")
                    if not divs.empty:
                        div_df = divs.tail(10).reset_index()
                        div_df.columns = ['Tanggal', 'Dividen (Rp)']
                        div_df['Tanggal'] = div_df['Tanggal'].dt.strftime('%Y-%m-%d')
                        st.dataframe(div_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("Tidak ada riwayat dividen.")
                with ca_col2:
                    st.markdown("#### 🔀 Riwayat Stock Split")
                    if not splits.empty:
                        split_df = splits.reset_index()
                        split_df.columns = ['Tanggal', 'Rasio']
                        split_df['Tanggal'] = split_df['Tanggal'].dt.strftime('%Y-%m-%d')
                        st.dataframe(split_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("Tidak ada riwayat split.")


# ───────────────────────────────────────────────
# MODUL 3: BREAKOUT SCREENER (UPDATED dengan filter aktif)
# ───────────────────────────────────────────────
elif menu == "🚀 Breakout Screener":
    st.subheader("🚀 Breakout Screener — MA20 & MA50 + Volume Surge")
    st.markdown(f"""
    Screener mendeteksi saham breakout dari **{len(ticker_df)} emiten aktif** 
    (saham suspend otomatis di-skip).
    """)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        vol_threshold = st.slider("🔊 Volume Threshold", 1.0, 5.0, 1.5, 0.1)
    with col2:
        max_scan = st.slider(
            "🎯 Jumlah Discan", 10, len(ticker_df),
            min(50, len(ticker_df))
        )
    with col3:
        skip_watchlist = st.checkbox("Skip Pemantauan Khusus", value=True,
                                      help="Skip saham di papan watch list")
    
    if st.button("🔥 Jalankan Screener", use_container_width=True):
        # Filter universe
        scan_df = ticker_df.copy()
        if skip_watchlist and 'board' in scan_df.columns:
            scan_df = scan_df[~scan_df['board'].astype(str).str.contains('Pemantauan', na=False)]
        
        results = []
        skipped_suspended = 0
        progress = st.progress(0, text="Memulai scan...")
        tickers_to_scan = scan_df['ticker'].tolist()[:max_scan]
        
        for i, tk in enumerate(tickers_to_scan):
            progress.progress((i+1)/len(tickers_to_scan),
                             text=f"Scanning {tk} ({i+1}/{len(tickers_to_scan)})")
            
            df = fetch_stock_data(tk, period="6mo")
            
            # Skip jika data kosong (kemungkinan suspend)
            if df is None or df.empty:
                skipped_suspended += 1
                continue
            
            # Skip jika volume 5 hari terakhir = 0 (suspend confirmed)
            if df['Volume'].tail(5).sum() == 0:
                skipped_suspended += 1
                continue
            
            df = calculate_indicators(df)
            sig = detect_breakout_signal(df, volume_threshold=vol_threshold)
            
            if sig['signal']:
                row = scan_df[scan_df['ticker']==tk].iloc[0]
                results.append({
                    'Ticker': tk,
                    'Nama': row['name'],
                    'Sektor': row['sector'],
                    'Papan': row.get('board', '-'),
                    'Close': sig['close'],
                    'MA20': sig['ma20'],
                    'MA50': sig['ma50'],
                    'Vol Ratio': sig['volume_ratio'],
                    'RSI': sig['rsi']
                })
        
        progress.empty()
        
        st.info(f"📊 Scan selesai: {len(tickers_to_scan)} saham dianalisa, "
                f"{skipped_suspended} di-skip (suspend/no-data).")
        
        if results:
            st.success(f"🎯 **{len(results)} saham** terdeteksi breakout!")
            res_df = pd.DataFrame(results).sort_values('Vol Ratio', ascending=False)
            st.dataframe(
                res_df.style.format({
                    'Close': 'Rp {:,.0f}', 'MA20': 'Rp {:,.0f}',
                    'MA50': 'Rp {:,.0f}', 'Vol Ratio': '{:.2f}x', 'RSI': '{:.1f}'
                }).background_gradient(subset=['Vol Ratio'], cmap='Greens'),
                use_container_width=True, hide_index=True
            )
            csv = res_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Hasil (CSV)", csv,
                              "breakout_signals.csv", "text/csv")
        else:
            st.info("📭 Tidak ada saham yang memenuhi kriteria breakout saat ini.")


# ───────────────────────────────────────────────
# MODUL 4: CORPORATE ACTION SCREENER
# ───────────────────────────────────────────────
elif menu == "💰 Corporate Action Screener":
    st.subheader("💰 Corporate Action Screener")
    
    sub_menu = st.radio(
        "Pilih Tipe:",
        ["💵 Dividend Yield Ranker", "🔀 Recent Stock Splits"],
        horizontal=True
    )
    
    max_scan_ca = st.slider("Jumlah saham discan:", 10, len(ticker_df),
                            min(100, len(ticker_df)))
    
    if sub_menu == "💵 Dividend Yield Ranker":
        if st.button("🚀 Jalankan Ranker", use_container_width=True):
            results = []
            progress = st.progress(0)
            tickers_list = ticker_df['ticker'].tolist()[:max_scan_ca]
            for i, tk in enumerate(tickers_list):
                progress.progress((i+1)/len(tickers_list))
                info = fetch_stock_info(tk)
                dy = info.get('dividendYield', 0)
                if dy and dy > 0:
                    name = ticker_df[ticker_df['ticker']==tk]['name'].values[0]
                    results.append({
                        'Ticker': tk, 'Nama': name,
                        'Div Yield (%)': dy * 100,
                        'Payout Ratio': info.get('payoutRatio', 0) * 100 if info.get('payoutRatio') else 0,
                        'PER': info.get('trailingPE', 0)
                    })
            progress.empty()
            if results:
                df_res = pd.DataFrame(results).sort_values('Div Yield (%)', ascending=False)
                st.dataframe(
                    df_res.style.format({
                        'Div Yield (%)': '{:.2f}%', 'Payout Ratio': '{:.2f}%', 'PER': '{:.2f}'
                    }).background_gradient(subset=['Div Yield (%)'], cmap='YlGn'),
                    use_container_width=True, hide_index=True
                )
    else:
        if st.button("🔍 Cek Stock Splits", use_container_width=True):
            results = []
            progress = st.progress(0)
            tickers_list = ticker_df['ticker'].tolist()[:max_scan_ca]
            for i, tk in enumerate(tickers_list):
                progress.progress((i+1)/len(tickers_list))
                _, splits = fetch_corporate_actions(tk)
                if not splits.empty:
                    last_split = splits.tail(1)
                    for date, ratio in last_split.items():
                        results.append({
                            'Ticker': tk,
                            'Tanggal Split Terakhir': date.strftime('%Y-%m-%d'),
                            'Rasio': f"{ratio:.2f}"
                        })
            progress.empty()
            if results:
                df_res = pd.DataFrame(results).sort_values(
                    'Tanggal Split Terakhir', ascending=False)
                st.dataframe(df_res, use_container_width=True, hide_index=True)
            else:
                st.info("Tidak ada data split tersedia.")


# ───────────────────────────────────────────────
# MODUL 5: FUNDAMENTAL RANKER
# ───────────────────────────────────────────────
elif menu == "📊 Fundamental Ranker":
    st.subheader("📊 Fundamental Ranker")
    
    rank_by = st.selectbox(
        "Ranking by:",
        ["ROE (Tertinggi)", "PER (Terendah - Value)",
         "PBV (Terendah - Value)", "Profit Margin (Tertinggi)"]
    )
    max_scan_f = st.slider("Jumlah saham discan:", 10, len(ticker_df),
                           min(100, len(ticker_df)))
    
    if st.button("🏆 Generate Ranking", use_container_width=True):
        results = []
        progress = st.progress(0)
        tickers_list = ticker_df['ticker'].tolist()[:max_scan_f]
        for i, tk in enumerate(tickers_list):
            progress.progress((i+1)/len(tickers_list))
            info = fetch_stock_info(tk)
            name = ticker_df[ticker_df['ticker']==tk]['name'].values[0]
            results.append({
                'Ticker': tk, 'Nama': name,
                'PER': info.get('trailingPE', np.nan),
                'PBV': info.get('priceToBook', np.nan),
                'ROE (%)': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else np.nan,
                'Profit Margin (%)': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else np.nan,
                'Market Cap (T)': info.get('marketCap', 0) / 1e12 if info.get('marketCap') else 0
            })
        progress.empty()
        df_res = pd.DataFrame(results).dropna(subset=['PER', 'PBV', 'ROE (%)'])
        sort_map = {
            "ROE (Tertinggi)": ('ROE (%)', False),
            "PER (Terendah - Value)": ('PER', True),
            "PBV (Terendah - Value)": ('PBV', True),
            "Profit Margin (Tertinggi)": ('Profit Margin (%)', False)
        }
        col, asc = sort_map[rank_by]
        df_res = df_res.sort_values(col, ascending=asc).head(20)
        st.dataframe(
            df_res.style.format({
                'PER': '{:.2f}', 'PBV': '{:.2f}',
                'ROE (%)': '{:.2f}%', 'Profit Margin (%)': '{:.2f}%',
                'Market Cap (T)': 'Rp {:.2f}T'
            }).background_gradient(subset=[col], cmap='RdYlGn_r' if asc else 'RdYlGn'),
            use_container_width=True, hide_index=True
        )


# ════════════════════════════════════════════════════════════════
# SECTION 10: FOOTER
# ════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#666; padding:1rem;'>"
    "⚠️ <i>Disclaimer: Platform untuk edukasi & riset. "
    "Bukan rekomendasi jual-beli. DYOR.</i><br>"
    f"🚀 <b>AlphaQuant IDX v2.0</b> | Universe: {len(ticker_df)} emiten aktif"
    "</div>", unsafe_allow_html=True
)
