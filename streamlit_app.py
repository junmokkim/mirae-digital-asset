import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import timedelta
import re

# =============================================================================
# 1. 초기 설정 및 스타일 -----------------------------------------------------------------
# =============================================================================

st.set_page_config(layout="wide")

# --- FRED API KEY 설정 (secrets 우선, 예외 시 기본값) ---
try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
except (FileNotFoundError, KeyError):
    FRED_API_KEY = '2f8671e0ca92ead96539311a2fb0d1fb'

# --- 전역 스타일(CSS) 적용 : UI 일관성 및 margin 조정 ---
st.markdown("""
<style>
    .block-container {padding-top:1.5rem; padding-bottom:1rem;}
    .stMetric {
        background-color: #fafafa; border: 1px solid #eee; border-radius: 8px; padding: 10px;
        margin-bottom: 12px !important;
    }
    .stMetricLabel {font-size:0.98rem !important; font-weight:600 !important;}
    .stMetricValue {font-size:1.6rem !important; line-height: 1.4;}
    .delta-indicator {
        font-size:0.98rem !important; font-weight:600 !important; margin-left:4px; letter-spacing: -0.01em;
    }
    .chart-date-info {font-size:0.82rem; color:gray; text-align:right; margin-top:-15px;}
    h1 { font-size:1.8rem !important; font-weight:700; margin-bottom:1.5rem; }
    h2 { font-size:1.3rem !important; font-weight:600; border-bottom: 2px solid #eee; padding-bottom:0.5rem; margin-top:1rem; margin-bottom:1rem;}
    h3.section-subheader { font-size:1.1rem; font-weight:600; margin-top:0.6rem; margin-bottom:0.8rem; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. 데이터 로딩 및 처리 함수 ----------------------------------------------------------
# =============================================================================

@st.cache_data(ttl=timedelta(hours=6))
def get_fred_series(series_id, label):
    """
    FRED API로부터 특정 시계열 데이터를 불러와 DataFrame으로 반환합니다.
    CPIAUCSL(미국 CPI)의 경우 12개월 YoY 변화율로 변환.
    """
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {'series_id': series_id, 'api_key': FRED_API_KEY, 'file_type': 'json'}
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        obs = r.json()['observations']
        df = pd.DataFrame(obs)
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df[['date', 'value']].rename(columns={'date': 'Date', 'value': label})
        df = df.sort_values('Date').dropna()

        # CPIAUCSL(소비자물가)은 YoY %로 변환
        if series_id == 'CPIAUCSL':
            df[label] = (df[label].pct_change(periods=12)) * 100
            df = df.dropna()
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"{series_id} 데이터 로딩 실패: {e}")
        return pd.DataFrame()
    except (KeyError, ValueError) as e:
        st.error(f"{series_id} 데이터 처리 중 오류 발생: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=timedelta(minutes=10))
def get_defillama_stablecoins():
    """
    DefiLlama API를 통해 현재 스테이블코인별 시가총액 리스트를 반환합니다.
    """
    url = "https://stablecoins.llama.fi/stablecoins?includePrices=true"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json().get('peggedAssets', [])
        if not data:
            st.warning("DefiLlama에서 스테이블코인 데이터를 가져오지 못했습니다.")
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if 'circulating' in df.columns:
            df['marketcap'] = df['circulating'].apply(lambda x: x.get('peggedUSD', 0) if isinstance(x, dict) else 0)
        else:
            df['marketcap'] = 0
        df = df[df['marketcap'] > 1_000_000]  # 100만달러 미만은 제외
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"DefiLlama API 호출 실패: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=timedelta(hours=1))
def get_defillama_historical_total_mcap():
    """
    DefiLlama API를 통해 전체 스테이블코인 시가총액의 시계열(과거) 데이터를 반환합니다.
    """
    url = "https://stablecoins.llama.fi/stablecoincharts/all"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['date'], unit='s')
        df = df[['Date', 'totalCirculatingUSD']]
        df['Total Market Cap ($B)'] = df['totalCirculatingUSD'].apply(lambda x: x.get('peggedUSD', 0) / 1e9)
        df = df[['Date', 'Total Market Cap ($B)']].sort_values('Date').dropna()
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"DefiLlama 시계열 데이터 호출 실패: {e}")
        return pd.DataFrame()

def last_data_info(df, freq):
    """
    데이터프레임의 최신 날짜와 데이터 주기를 포맷팅하여 반환.
    """
    if df.empty: return "데이터 없음"
    last_date = df['Date'].iloc[-1].date()
    return f"최근 데이터: <b>{last_date}</b> | FRED 공개 주기: <b>{freq}</b>"

# =============================================================================
# 3. 변화량(Delta) 계산 및 차트 그리기 함수 ----------------------------------------
# =============================================================================

def calculate_delta_html(df, column_name, delta_period_days, delta_direction, delta_label):
    """
    변화량(Delta) 텍스트 HTML 생성 함수.
    - delta_direction: 'normal'이면 증가=녹색, 'inverse'면 증가=빨간색
    """
    if df.empty or len(df) < 2: return ""
    df = df.sort_values('Date')
    latest_row = df.iloc[-1]
    latest_value = latest_row[column_name]
    latest_date = latest_row['Date']
    
    previous_date_target = latest_date - pd.Timedelta(days=delta_period_days)
    previous_df = df[df['Date'] <= previous_date_target]
    if previous_df.empty: return ""
    
    previous_value = previous_df.iloc[-1][column_name]
    delta = latest_value - previous_value
    if delta == 0: return ""

    # 단위 자동 추출
    unit_match = re.search(r'\((.*?)\)', column_name)
    unit = unit_match.group(1) if unit_match else ""
    if '%' in unit:
        formatter, unit_str = f"{abs(delta):,.2f}", '%p'
    elif '$B' in unit:
        formatter, unit_str = f"{abs(delta):,.2f}", " $B"
    elif '$M' in unit:
        formatter, unit_str = f"{abs(delta):,.0f}", " $M"
    else:
        formatter, unit_str = f"{abs(delta):,.1f}", ""
    formatted_delta_with_unit = f"{formatter}{unit_str}"
    
    is_positive_good = (delta_direction == 'normal')
    symbol, color = ("▲", "green" if is_positive_good else "red") if delta > 0 else ("▼", "red" if is_positive_good else "green")
    
    return f"<span class='delta-indicator' style='color:{color};'>({delta_label}: {symbol}{formatted_delta_with_unit})</span>"

def display_fred_chart(df, title, column_name, freq, selected_period, delta_periods, delta_direction, delta_labels):
    """
    FRED 등 지표의 라인차트 및 변화량 표시 함수.
    """
    if df.empty:
        st.warning(f"'{title}' 데이터를 표시할 수 없습니다.")
        return

    # 기간 슬라이싱
    period_map = {"6m": 180, "1y": 365, "5y": 1825, "전체": None}
    if period_map[selected_period]:
        start_date = df["Date"].max() - pd.Timedelta(days=period_map[selected_period])
        plot_df = df[df["Date"] >= start_date]
    else:
        plot_df = df

    # 변화량(Delta) HTML 생성
    delta_html_list = [
        calculate_delta_html(df, column_name, d, delta_direction, l)
        for d, l in zip(delta_periods, delta_labels)
    ]
    full_title = f"{title}" + "".join(delta_html_list)

    # 라인 차트
    fig = px.line(
        plot_df, x="Date", y=column_name,
        title=full_title,
        height=300
    )
    fig.update_layout(
        margin=dict(t=40, b=40, l=40, r=20),
        title_font_size=16,
        xaxis_title=None,
        yaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(
        f"<div class='chart-date-info'>{last_data_info(plot_df, freq)}</div>",
        unsafe_allow_html=True
    )

# =============================================================================
# 4. Streamlit UI 레이아웃 구성 ---------------------------------------------------
# =============================================================================

st.markdown("<h1>📊 미래에셋 경제 주체별 변화 모니터</h1>", unsafe_allow_html=True)

# --- 기간 선택 라디오 버튼 (기본값: 5y) ---
period_opts = ["6m", "1y", "5y", "전체"]
selected_period = st.radio(
    "차트 기간 선택", period_opts, index=2, horizontal=True, key="global_period"
)

# --- FRED 시리즈 정보(메타) 정의 ---
fred_series_info = {
    'central_bank': [
        {"id": "FEDFUNDS", "label": "Fed Funds Rate (%)", "title": "Fed 기준금리", "freq": "월간", "delta_periods": [30], "delta_direction": "inverse", "delta_labels": ["1개월"]},
        {"id": "WM2NS", "label": "M2 ($B)", "title": "M2 통화량($B)", "freq": "주간", "delta_periods": [90], "delta_direction": "normal", "delta_labels": ["3개월"]},
        {"id": "RRPONTSYD", "label": "Fed RRP ($B)", "title": "Fed 역레포(RRP) 규모 (높을수록 시중 유동성 감소)", "freq": "일간", "delta_periods": [30], "delta_direction": "inverse", "delta_labels": ["1개월"]},
    ],
    'financial_inst': [
        {"id": "DRTSCILM", "label": "Loan Standards (%)", "title": "SLOOS: 은행 대출 기준 (높을수록 대출 강화)", "freq": "분기별", "delta_periods": [90], "delta_direction": "inverse", "delta_labels": ["1분기"]},
        {"id": "TOTALSL", "label": "Consumer Credit ($M)", "title": "미국 가계 소비자신용 잔액($M)", "freq": "월간", "delta_periods": [90], "delta_direction": "inverse", "delta_labels": ["3개월"]},
    ],
    'corporations': [
        {"id": "BAMLC0A0CM", "label": "IG Spread (%)", "title": "투자등급(IG) 회사채 스프레드 (높을수록 리스크 증가)", "freq": "일간", "delta_periods": [30, 90], "delta_direction": "inverse", "delta_labels": ["1개월", "3개월"]},
        {"id": "BAMLH0A0HYM2", "label": "HY Spread (%)", "title": "하이일드(HY) 회사채 스프레드 (높을수록 리스크 증가)", "freq": "일간", "delta_periods": [30, 90], "delta_direction": "inverse", "delta_labels": ["1개월", "3개월"]},
    ],
    'households': [
        {"id": "CCLACBW027SBOG", "label": "Card Loan ($B)", "title": "상업은행 신용카드 대출 잔고($B)", "freq": "주간", "delta_periods": [30], "delta_direction": "inverse", "delta_labels": ["1개월"]},
        {"id": "CPIAUCSL", "label": "CPI YoY (%)", "title": "CPI(소비자물가지수) YoY", "freq": "월간", "delta_periods": [365], "delta_direction": "inverse", "delta_labels": ["1년"]},
    ]
}

# --- Streamlit 컬럼 배치 (2x2) ---
row1_col1, row1_col2 = st.columns(2)
row2_col1, row2_col2 = st.columns(2)

with row1_col1:
    st.markdown("<h2>🏦 연준 / 정책</h2>", unsafe_allow_html=True)
    for s in fred_series_info['central_bank']:
        df = get_fred_series(s["id"], s["label"])
        display_fred_chart(df, s["title"], s["label"], s["freq"], selected_period, s["delta_periods"], s["delta_direction"], s["delta_labels"])

with row1_col2:
    st.markdown("<h2>🏦 금융기관</h2>", unsafe_allow_html=True)
    for s in fred_series_info['financial_inst']:
        df = get_fred_series(s["id"], s["label"])
        display_fred_chart(df, s["title"], s["label"], s["freq"], selected_period, s["delta_periods"], s["delta_direction"], s["delta_labels"])
    
    # --- 금융기관 하위: 디지털 자산(스테이블코인) ---------------------------------------
    st.markdown('<h3 class="section-subheader">디지털 자산 (스테이블코인)</h3>', unsafe_allow_html=True)

    # 현재·과거 스테이블코인 시가총액 데이터 로딩
    df_stablecoins_now = get_defillama_stablecoins()
    df_stablecoins_hist = get_defillama_historical_total_mcap()
    total_stablecoin_mcap_now = df_stablecoins_now['marketcap'].sum() if not df_stablecoins_now.empty else 0

    # 변화량(Delta) 계산 (증가시 빨강)
    delta_1m_html = calculate_delta_html(df_stablecoins_hist, 'Total Market Cap ($B)', 30, 'inverse', '1개월')
    delta_3m_html = calculate_delta_html(df_stablecoins_hist, 'Total Market Cap ($B)', 90, 'inverse', '3개월')
    delta_htmls = [delta_1m_html, delta_3m_html]
    delta_html_joined = "".join(delta_htmls)

    # 스테이블코인 metric 표시
    st.markdown(f"""
        <div class="stMetric">
            <label class="stMetricLabel">
                총 스테이블코인 시가총액{delta_html_joined}
            </label>
            <p class="stMetricValue">${total_stablecoin_mcap_now/1e9:.2f} B</p>
        </div>
    """, unsafe_allow_html=True)
    
    # 주요 스테이블코인 시장 점유율 파이차트
    if not df_stablecoins_now.empty:
        df_stablecoins_sorted = df_stablecoins_now.sort_values('marketcap', ascending=False).head(7)
        fig_sc = px.pie(
            df_stablecoins_sorted, values='marketcap', names='name',
            title='주요 스테이블코인 시장 점유율', height=320, hole=0.4
        )
        fig_sc.update_traces(textposition='inside', textinfo='percent+label')
        fig_sc.update_layout(margin=dict(t=40, b=20, l=20, r=20), title_font_size=16, showlegend=False)
        st.plotly_chart(fig_sc, use_container_width=True)
        st.markdown(
            "<div class='chart-date-info' style='margin-top:-5px;'>출처: <b>DefiLlama</b> (실시간)</div>",
            unsafe_allow_html=True
        )
    
    # 스테이블코인 주요 준비금 관련 정보(Expander)
    with st.expander("주요 스테이블코인 준비금 정보 (Tether, Circle)"):
        st.info("Tether와 Circle은 실시간 준비금 API를 제공하지 않으며, 정기적인 감사/증명 보고서를 통해 투명성을 공개합니다.")
        st.markdown("""
        - **Tether (USDT) 투명성 보고서:** [https://tether.to/en/transparency/](https://tether.to/en/transparency/)
        - **Circle (USDC) 투명성 보고서:** [https://www.circle.com/en/transparency](https://www.circle.com/en/transparency)
        """)

with row2_col1:
    st.markdown("<h2>🏢 기업</h2>", unsafe_allow_html=True)
    for s in fred_series_info['corporations']:
        df = get_fred_series(s["id"], s["label"])
        display_fred_chart(df, s["title"], s["label"], s["freq"], selected_period, s["delta_periods"], s["delta_direction"], s["delta_labels"])

with row2_col2:
    st.markdown("<h2>👨‍👩‍👧‍👦 가계 (소비자)</h2>", unsafe_allow_html=True)
    for s in fred_series_info['households']:
        df = get_fred_series(s["id"], s["label"])
        display_fred_chart(df, s["title"], s["label"], s["freq"], selected_period, s["delta_periods"], s["delta_direction"], s["delta_labels"])