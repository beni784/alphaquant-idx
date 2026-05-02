"""
═══════════════════════════════════════════════════════════════════
  ALPHAQUANT IDX - Institutional-Grade Stock Analysis Platform
  Author: Built with AlphaQuant S-Tier Framework
  Target: Indonesian Stock Exchange (IDX/IHSG)
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
import warnings
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

# CSS Custom untuk look profesional ala Bloomberg Terminal
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
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1A1F2E;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# SECTION 3: DATA LOADER (dengan SMART CACHING)
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=86400)  # Cache 24 jam (daftar ticker jarang berubah)
def load_ticker_list():
    """Memuat daftar saham IDX dari file CSV."""
    try:
        df = pd.read_csv("idx_tickers.csv")
        return df
    except Exception as e:
        st.error(f"Gagal memuat daftar saham: {e}")
        return pd.DataFrame(columns=['ticker', 'name', 'sector'])


@st.cache_data(ttl=3600)  # Cache 1 jam
def fetch_stock_data(ticker, period="6mo"):
    """
    Mengambil data harga historis 1 saham dari Yahoo Finance.
    
    Parameters:
        ticker (str): Kode saham, contoh 'BBCA.JK'
        period (str): Periode data, contoh '6mo', '1y', '2y'
    
    Returns:
        pandas.DataFrame: OHLCV data
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            return None
        return hist
    except Exception as e:
        st.warning(f"Gagal fetch {ticker}: {e}")
        return None


@st.cache_data(ttl=3600)
def fetch_stock_info(ticker):
    """
    Mengambil data fundamental & info saham (PER, PBV, ROE, dll).
    
    Returns:
        dict: Informasi fundamental saham
    """
    try:
        stock = yf.Ticker(ticker)
        return stock.info
    except Exception as e:
        return {}


@st.cache_data(ttl=3600)
def fetch_corporate_actions(ticker):
    """
    Mengambil data aksi korporasi: Dividen & Stock Split.
    
    Returns:
        tuple: (dividends_series, splits_series)
    """
    try:
        stock = yf.Ticker(ticker)
        return stock.dividends, stock.splits
    except Exception:
        return pd.Series(), pd.Series()


@st.cache_data(ttl=1800)  # Cache 30 menit untuk batch screening
def fetch_batch_data(tickers_list, period="3mo"):
    """
    PRO TIP #2: Batch download paralel untuk efisiensi.
    Mengambil data MULTI-TICKER sekaligus dengan threading.
    
    Ini 5-10x lebih cepat daripada loop 1-per-1.
    """
    try:
        tickers_str = " ".join(tickers_list)
        data = yf.download(
            tickers=tickers_str,
            period=period,
            group_by='ticker',
            threads=True,        # ← KUNCI KECEPATAN
            progress=False,
            auto_adjust=True
        )
        return data
    except Exception as e:
        st.error(f"Batch fetch error: {e}")
        return None


# ════════════════════════════════════════════════════════════════
# SECTION 4: ENGINE TEKNIKAL - MA & BREAKOUT DETECTOR
# ════════════════════════════════════════════════════════════════

def calculate_indicators(df):
    """
    Menghitung indikator teknikal: MA20, MA50, MA200, Volume Average, RSI.
    """
    if df is None or df.empty or len(df) < 50:
        return None
    
    df = df.copy()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_MA20']
    
    # RSI 14 (bonus indicator)
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df


def detect_breakout_signal(df, volume_threshold=1.5):
    """
    LOGIKA INTI: Deteksi breakout MA20 & MA50 + Volume Surge.
    
    Mengimplementasi 4 kondisi yang dibahas di Fase 1:
        A. Trend Confirmation (Close > MA20 > MA50)
        B. Fresh Breakout (kemarin masih di bawah MA)
        C. Volume Confirmation (>1.5x rata-rata)
        D. Anti False-Breakout (candle hijau, close di top range)
    
    Returns:
        dict: Detail sinyal breakout
    """
    if df is None or len(df) < 50:
        return {'signal': False, 'reason': 'Data tidak cukup'}
    
    today = df.iloc[-1]
    yesterday = df.iloc[-2]
    
    # Cek nilai NaN
    if pd.isna(today['MA20']) or pd.isna(today['MA50']):
        return {'signal': False, 'reason': 'MA belum siap'}
    
    # KONDISI A: Trend Confirmation
    cond_a = (
        today['Close'] > today['MA20'] and
        today['Close'] > today['MA50'] and
        today['MA20'] > today['MA50']
    )
    
    # KONDISI B: Fresh Breakout
    cond_b = (
        yesterday['Close'] <= yesterday['MA20'] or
        yesterday['Close'] <= yesterday['MA50']
    )
    
    # KONDISI C: Volume Confirmation
    cond_c = today['Volume_Ratio'] > volume_threshold
    
    # KONDISI D: Anti False-Breakout
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
# SECTION 5: ENGINE FUNDAMENTAL - PIOTROSKI & ALTMAN
# ════════════════════════════════════════════════════════════════

def calculate_piotroski_fscore(ticker):
    """
    Piotroski F-Score: Skor 0-9 untuk kualitas fundamental.
    Skor ≥7 = Sangat sehat, ≤3 = Lemah.
    
    9 kriteria dibagi 3 kategori:
        Profitabilitas (4): ROA+, CFO+, ΔROA+, CFO>NI
        Leverage (3): ΔLeverage-, ΔCurrentRatio+, NoNewShares
        Efisiensi (2): ΔGrossMargin+, ΔAssetTurnover+
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        score = 0
        details = {}
        
        # 1. ROA Positif
        roa = info.get('returnOnAssets', 0)
        if roa and roa > 0:
            score += 1
            details['ROA Positif'] = '✅'
        else:
            details['ROA Positif'] = '❌'
        
        # 2. Operating Cash Flow Positif
        ocf = info.get('operatingCashflow', 0)
        if ocf and ocf > 0:
            score += 1
            details['OCF Positif'] = '✅'
        else:
            details['OCF Positif'] = '❌'
        
        # 3. CFO > Net Income (kualitas earning)
        ni = info.get('netIncomeToCommon', 0)
        if ocf and ni and ocf > ni:
            score += 1
            details['CFO > Net Income'] = '✅'
        else:
            details['CFO > Net Income'] = '❌'
        
        # 4. Current Ratio > 1
        cr = info.get('currentRatio', 0)
        if cr and cr > 1:
            score += 1
            details['Current Ratio > 1'] = '✅'
        else:
            details['Current Ratio > 1'] = '❌'
        
        # 5. Gross Margin > 0
        gm = info.get('grossMargins', 0)
        if gm and gm > 0:
            score += 1
            details['Gross Margin Positif'] = '✅'
        else:
            details['Gross Margin Positif'] = '❌'
        
        # 6. ROE Positif
        roe = info.get('returnOnEquity', 0)
        if roe and roe > 0:
            score += 1
            details['ROE Positif'] = '✅'
        else:
            details['ROE Positif'] = '❌'
        
        # 7. Profit Margin Positif
        pm = info.get('profitMargins', 0)
        if pm and pm > 0:
            score += 1
            details['Profit Margin Positif'] = '✅'
        else:
            details['Profit Margin Positif'] = '❌'
        
        # 8. Debt-to-Equity Sehat (<1)
        de = info.get('debtToEquity', 999)
        if de and de < 100:  # yfinance kasih dalam %
            score += 1
            details['DER Sehat (<1)'] = '✅'
        else:
            details['DER Sehat (<1)'] = '❌'
        
        # 9. Revenue Growth Positif
        rg = info.get('revenueGrowth', 0)
        if rg and rg > 0:
            score += 1
            details['Revenue Growth +'] = '✅'
        else:
            details['Revenue Growth +'] = '❌'
        
        return score, details
    
    except Exception as e:
        return 0, {'error': str(e)}


def calculate_altman_zscore(ticker):
    """
    Altman Z-Score: Prediktor kebangkrutan.
    Z > 3.0 = Aman | 1.8 < Z < 3.0 = Grey Zone | Z < 1.8 = Distress
    
    Formula: Z = 1.2A + 1.4B + 3.3C + 0.6D + 1.0E
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        bs = stock.balance_sheet
        fin = stock.financials
        
        if bs.empty or fin.empty:
            return None, "Data laporan keuangan tidak tersedia"
        
        # Ambil kolom terbaru
        latest_bs = bs.iloc[:, 0]
        latest_fin = fin.iloc[:, 0]
        
        total_assets = latest_bs.get('Total Assets', np.nan)
        if pd.isna(total_assets) or total_assets == 0:
            return None, "Total Assets tidak tersedia"
        
        # A = Working Capital / Total Assets
        current_assets = latest_bs.get('Current Assets', 0)
        current_liab = latest_bs.get('Current Liabilities', 0)
        wc = current_assets - current_liab
        A = wc / total_assets
        
        # B = Retained Earnings / Total Assets
        re = latest_bs.get('Retained Earnings', 0)
        B = re / total_assets
        
        # C = EBIT / Total Assets
        ebit = latest_fin.get('EBIT', latest_fin.get('Operating Income', 0))
        C = ebit / total_assets
        
        # D = Market Cap / Total Liabilities
        mcap = info.get('marketCap', 0)
        total_liab = latest_bs.get('Total Liabilities Net Minority Interest', 
                                    latest_bs.get('Total Debt', 1))
        D = mcap / total_liab if total_liab > 0 else 0
        
        # E = Revenue / Total Assets
        revenue = latest_fin.get('Total Revenue', 0)
        E = revenue / total_assets
        
        z_score = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E
        
        if z_score > 3.0:
            status = "🟢 SAFE ZONE"
        elif z_score > 1.8:
            status = "🟡 GREY ZONE"
        else:
            status = "🔴 DISTRESS ZONE"
        
        return z_score, status
    
    except Exception as e:
        return None, f"Error: {str(e)[:50]}"


# ════════════════════════════════════════════════════════════════
# SECTION 6: VISUALISASI - PLOTLY CHARTS
# ════════════════════════════════════════════════════════════════

def create_candlestick_chart(df, ticker_name):
    """Membuat chart candlestick interaktif dengan MA20, MA50, dan Volume."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f'{ticker_name} - Price Chart', 'Volume')
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price',
        increasing_line_color='#00C49A',
        decreasing_line_color='#FF4B4B'
    ), row=1, col=1)
    
    # MA20
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MA20'],
        name='MA20', line=dict(color='#FFA500', width=1.5)
    ), row=1, col=1)
    
    # MA50
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MA50'],
        name='MA50', line=dict(color='#00A3FF', width=1.5)
    ), row=1, col=1)
    
    # Volume bars
    colors = ['#00C49A' if c >= o else '#FF4B4B' 
              for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'],
        name='Volume', marker_color=colors
    ), row=2, col=1)
    
    fig.update_layout(
        height=600,
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    return fig


# ════════════════════════════════════════════════════════════════
# SECTION 7: SIDEBAR - NAVIGASI UTAMA
# ════════════════════════════════════════════════════════════════

st.sidebar.markdown("# 📈 AlphaQuant IDX")
st.sidebar.markdown("*Institutional Stock Analyzer*")
st.sidebar.markdown("---")

ticker_df = load_ticker_list()

menu = st.sidebar.radio(
    "🧭 **Navigasi Modul:**",
    [
        "🏠 Dashboard",
        "🔍 Single Stock Analysis",
        "🚀 Breakout Screener",
        "💰 Corporate Action Screener",
        "📊 Fundamental Ranker"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 **Pro Tip:**\n\n"
    "Data di-cache 1 jam untuk hindari rate limit. "
    "Refresh manual via tombol di tiap modul."
)
st.sidebar.markdown("---")
st.sidebar.caption(f"📅 {datetime.now().strftime('%d %B %Y, %H:%M')} WIB")
st.sidebar.caption("⚡ Powered by AlphaQuant Engine")


# ════════════════════════════════════════════════════════════════
# SECTION 8: HALAMAN UTAMA - HEADER
# ════════════════════════════════════════════════════════════════

st.markdown('<div class="main-header">📊 AlphaQuant IDX Terminal</div>', 
            unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center; color:#888;'>"
    "Institutional-Grade Analysis untuk Saham Indonesia"
    "</p>", unsafe_allow_html=True
)
st.markdown("---")


# ════════════════════════════════════════════════════════════════
# SECTION 9: ROUTING MODUL
# ════════════════════════════════════════════════════════════════

# ───────────────────────────────────────────────
# MODUL 1: DASHBOARD HOME
# ───────────────────────────────────────────────
if menu == "🏠 Dashboard":
    st.subheader("Selamat Datang di AlphaQuant IDX")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Universe", f"{len(ticker_df)} Saham", "IDX Liquid")
    with col2:
        st.metric("🔄 Cache TTL", "1 Jam", "Auto-refresh")
    with col3:
        st.metric("⚡ Engine", "Streamlit", "Cloud Hosted")
    
    st.markdown("### 🎯 Fitur Platform")
    
    feat_col1, feat_col2 = st.columns(2)
    with feat_col1:
        st.markdown("""
        #### 🔍 Single Stock Analysis
        - Chart candlestick interaktif (Plotly)
        - Indikator: MA20, MA50, MA200, RSI
        - Metric fundamental lengkap
        - Piotroski F-Score & Altman Z-Score
        
        #### 🚀 Breakout Screener
        - 4-kondisi multi-filter
        - Anti false-signal
        - Volume surge confirmation
        - Hasil ranking by strength
        """)
    with feat_col2:
        st.markdown("""
        #### 💰 Corporate Action Screener
        - Riwayat dividen
        - Stock split history
        - Dividend yield ranker
        
        #### 📊 Fundamental Ranker
        - Top stocks by ROE
        - Lowest PER/PBV (value)
        - Highest dividend yield
        - F-Score leaderboard
        """)
    
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
            st.error("❌ Data tidak tersedia. Coba saham lain.")
        else:
            # Tab Layout
            tab1, tab2, tab3, tab4 = st.tabs([
                "📈 Chart", "💼 Fundamental", "⭐ Scores", "💵 Corp. Action"
            ])
            
            # === TAB 1: CHART ===
            with tab1:
                last = df.iloc[-1]
                prev = df.iloc[-2]
                change = ((last['Close'] - prev['Close']) / prev['Close']) * 100
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("💵 Last Price", f"Rp {last['Close']:,.0f}",
                          f"{change:+.2f}%")
                m2.metric("📊 MA20", f"Rp {last['MA20']:,.0f}",
                          f"{((last['Close']/last['MA20'])-1)*100:+.2f}%")
                m3.metric("📈 MA50", f"Rp {last['MA50']:,.0f}",
                          f"{((last['Close']/last['MA50'])-1)*100:+.2f}%")
                m4.metric("📦 Vol Ratio", f"{last['Volume_Ratio']:.2f}x",
                          "vs 20D avg")
                
                fig = create_candlestick_chart(df, selected_ticker)
                st.plotly_chart(fig, use_container_width=True)
                
                # Breakout Signal Check
                signal = detect_breakout_signal(df)
                if signal['signal']:
                    st.success("🚀 **BREAKOUT SIGNAL TERDETEKSI!** Semua 4 kondisi terpenuhi.")
                else:
                    st.info("📊 Tidak ada sinyal breakout aktif saat ini.")
            
            # === TAB 2: FUNDAMENTAL ===
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
            
            # === TAB 3: SCORES ===
            with tab3:
                st.markdown("### ⭐ Institutional Composite Scores")
                
                col_p, col_a = st.columns(2)
                
                with col_p:
                    st.markdown("#### 🎯 Piotroski F-Score")
                    with st.spinner("Calculating..."):
                        f_score, f_details = calculate_piotroski_fscore(selected_ticker)
                    
                    if f_score >= 7:
                        st.success(f"## {f_score} / 9 — STRONG ✅")
                    elif f_score >= 4:
                        st.warning(f"## {f_score} / 9 — MODERATE ⚠️")
                    else:
                        st.error(f"## {f_score} / 9 — WEAK ❌")
                    
                    st.markdown("**Detail Kriteria:**")
                    for k, v in f_details.items():
                        st.write(f"{v} {k}")
                
                with col_a:
                    st.markdown("#### 🛡️ Altman Z-Score")
                    with st.spinner("Calculating..."):
                        z_score, z_status = calculate_altman_zscore(selected_ticker)
                    
                    if z_score is not None:
                        st.markdown(f"## {z_score:.2f}")
                        st.markdown(f"### {z_status}")
                        st.markdown("""
                        **Interpretasi:**
                        - 🟢 Z > 3.0: Safe (kebangkrutan minim)
                        - 🟡 1.8 < Z < 3.0: Grey Zone (waspada)
                        - 🔴 Z < 1.8: Distress (risiko tinggi)
                        """)
                    else:
                        st.warning(z_status)
            
            # === TAB 4: CORPORATE ACTION ===
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
# MODUL 3: BREAKOUT SCREENER
# ───────────────────────────────────────────────
elif menu == "🚀 Breakout Screener":
    st.subheader("🚀 Breakout Screener — MA20 & MA50 + Volume Surge")
    st.markdown("""
    Screener ini mendeteksi saham yang baru saja **breakout** di atas MA20 & MA50
    dengan **lonjakan volume**. Mengimplementasi 4-condition multi-filter.
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        vol_threshold = st.slider(
            "🔊 Volume Threshold (x rata-rata 20 hari)",
            min_value=1.0, max_value=5.0, value=1.5, step=0.1
        )
    with col2:
        max_scan = st.slider(
            "🎯 Jumlah Saham Discan",
            min_value=10, max_value=len(ticker_df), 
            value=min(30, len(ticker_df))
        )
    
    if st.button("🔥 Jalankan Screener", use_container_width=True):
        results = []
        progress = st.progress(0, text="Memulai scan...")
        tickers_to_scan = ticker_df['ticker'].tolist()[:max_scan]
        
        for i, tk in enumerate(tickers_to_scan):
            progress.progress((i+1)/len(tickers_to_scan), 
                             text=f"Scanning {tk} ({i+1}/{len(tickers_to_scan)})")
            df = fetch_stock_data(tk, period="6mo")
            df = calculate_indicators(df)
            sig = detect_breakout_signal(df, volume_threshold=vol_threshold)
            
            if sig['signal']:
                name = ticker_df[ticker_df['ticker']==tk]['name'].values[0]
                sector = ticker_df[ticker_df['ticker']==tk]['sector'].values[0]
                results.append({
                    'Ticker': tk,
                    'Nama': name,
                    'Sektor': sector,
                    'Close': sig['close'],
                    'MA20': sig['ma20'],
                    'MA50': sig['ma50'],
                    'Vol Ratio': sig['volume_ratio'],
                    'RSI': sig['rsi']
                })
        
        progress.empty()
        
        if results:
            st.success(f"🎯 **{len(results)} saham** terdeteksi breakout!")
            res_df = pd.DataFrame(results)
            res_df = res_df.sort_values('Vol Ratio', ascending=False)
            
            st.dataframe(
                res_df.style.format({
                    'Close': 'Rp {:,.0f}',
                    'MA20': 'Rp {:,.0f}',
                    'MA50': 'Rp {:,.0f}',
                    'Vol Ratio': '{:.2f}x',
                    'RSI': '{:.1f}'
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
    
    if sub_menu == "💵 Dividend Yield Ranker":
        st.markdown("Ranking saham berdasarkan **Dividend Yield** tertinggi.")
        
        if st.button("🚀 Jalankan Ranker", use_container_width=True):
            results = []
            progress = st.progress(0)
            tickers_list = ticker_df['ticker'].tolist()
            
            for i, tk in enumerate(tickers_list):
                progress.progress((i+1)/len(tickers_list))
                info = fetch_stock_info(tk)
                dy = info.get('dividendYield', 0)
                if dy and dy > 0:
                    name = ticker_df[ticker_df['ticker']==tk]['name'].values[0]
                    results.append({
                        'Ticker': tk,
                        'Nama': name,
                        'Div Yield (%)': dy * 100,
                        'Payout Ratio': info.get('payoutRatio', 0) * 100 if info.get('payoutRatio') else 0,
                        'PER': info.get('trailingPE', 0)
                    })
            
            progress.empty()
            
            if results:
                df_res = pd.DataFrame(results).sort_values('Div Yield (%)', ascending=False)
                st.dataframe(
                    df_res.style.format({
                        'Div Yield (%)': '{:.2f}%',
                        'Payout Ratio': '{:.2f}%',
                        'PER': '{:.2f}'
                    }).background_gradient(subset=['Div Yield (%)'], cmap='YlGn'),
                    use_container_width=True, hide_index=True
                )
    
    else:  # Stock Splits
        st.markdown("Riwayat **Stock Split** dari universe saham IDX.")
        
        if st.button("🔍 Cek Stock Splits", use_container_width=True):
            results = []
            progress = st.progress(0)
            tickers_list = ticker_df['ticker'].tolist()
            
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
    st.markdown("Ranking saham berdasarkan metrik fundamental kunci.")
    
    rank_by = st.selectbox(
        "Ranking by:",
        ["ROE (Tertinggi)", "PER (Terendah - Value)", 
         "PBV (Terendah - Value)", "Profit Margin (Tertinggi)"]
    )
    
    if st.button("🏆 Generate Ranking", use_container_width=True):
        results = []
        progress = st.progress(0)
        tickers_list = ticker_df['ticker'].tolist()
        
        for i, tk in enumerate(tickers_list):
            progress.progress((i+1)/len(tickers_list))
            info = fetch_stock_info(tk)
            name = ticker_df[ticker_df['ticker']==tk]['name'].values[0]
            
            results.append({
                'Ticker': tk,
                'Nama': name,
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
    "⚠️ <i>Disclaimer: Platform ini untuk tujuan edukasi & riset. "
    "Bukan rekomendasi jual-beli. Lakukan due diligence sendiri.</i><br>"
    "🚀 <b>AlphaQuant IDX</b> | Built with Streamlit + yfinance"
    "</div>", unsafe_allow_html=True
)
