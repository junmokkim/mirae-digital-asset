import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import timedelta
import re

# --- 1. 초기 설정 및 스타일 ---
st.set_page_config(layout="wide")

try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
except (FileNotFoundError, KeyError):
    FRED_API_KEY = '2f8671e0ca92ead96539311a2fb0d1fb'

st.markdown("""
<style>
    .block-container {padding-top:1.5rem; padding-bottom:1rem;}
    .stMetricLabel {font-size:0.98rem !important;}
    .chart-date-info {font-size:0.82rem; color:gray; text-align:right; margin-top:-15px;}
    h1 { font-size:1.8rem !important; font-weight:700; margin-bottom:1.5rem; }
    h2 { font-size:1.3rem !important; font-weight:600; border-bottom: 2px solid #eee; padding-bottom:0.5rem; margin-top:1rem; margin-bottom:1rem;}
</style>
""", unsafe_allow_html=True)


# --- 2. 데이터 로딩 및 처리 함수 ---
@st.cache_data(ttl=timedelta(hours=6))
def get_fred_series(series_id, label):
    url = f"https://api.stlouisfed.org/fred/series/observations"
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

        # CPIAUCSL 시리즈에 대한 YOY 계산
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

@st.cache_data(ttl=timedelta(minutes=5))
def get_stablecoin_data():
    coins = ['tether', 'usd-coin', 'dai']
    try:
        resp = requests.get('https://api.coingecko.com/api/v3/coins/markets', params={'vs_currency':'usd','ids':','.join(coins)})
        resp.raise_for_status()
        df_sc = pd.DataFrame(resp.json())[['name', 'market_cap']]
        return df_sc
    except requests.exceptions.RequestException as e:
        st.error(f"CoinGecko API 호출 실패: {e}")
        return pd.DataFrame()

def last_data_info(df, freq):
    if df.empty: return "데이터 없음"
    last_date = df['Date'].iloc[-1].date()
    return f"최근 데이터: <b>{last_date}</b> | FRED 공개 주기: <b>{freq}</b>"

# --- 3. 변화량 계산 및 차트 생성 함수 ---
def calculate_delta_html(df, column_name, delta_period_days, delta_direction, delta_label):
    if df.empty or len(df) < 2:
        return ""

    latest_row = df.iloc[-1]
    latest_value = latest_row[column_name]
    latest_date = latest_row['Date']

    previous_date_target = latest_date - pd.Timedelta(days=delta_period_days)
    previous_df = df[df['Date'] <= previous_date_target]

    if previous_df.empty: return ""

    previous_value = previous_df.iloc[-1][column_name]
    delta = latest_value - previous_value
    
    # delta가 0이 아닌 경우에만 델타 값을 표시
    if delta == 0:
        return ""

    # 단위 추출 및 포맷팅 개선
    unit_match = re.search(r'\((.*?)\)', column_name)
    unit = unit_match.group(1) if unit_match else ""

    if '%' in unit:
        # 퍼센트 지표의 변화량을 %p로 표시
        if 'Spread' in column_name or 'CPI YoY' in column_name:
            formatter = f"{abs(delta):,.2f}"
            unit = '%p'
        else:
            formatter = f"{abs(delta):,.2f}"
    elif 'Index' in unit:
        formatter = f"{abs(delta):,.1f}"
    elif '$M' in unit: # 백만 달러 단위 포맷팅 추가
        formatter = f"{abs(delta):,.0f}" # 소수점 없이 표시
    else: # Billion $
        formatter = f"{abs(delta):,.2f}"
    
    formatted_delta_with_unit = f"{formatter}{unit}"

    is_positive_good = (delta_direction == 'normal')
    if delta > 0:
        symbol, color = "▲", "green" if is_positive_good else "red"
    else:
        symbol, color = "▼", "red" if is_positive_good else "green"

    return f" <span style='font-size:0.85em; color:{color};'>({delta_label}: {symbol}{formatted_delta_with_unit})</span>"

def display_fred_chart(df, title, column_name, freq, selected_period, delta_periods, delta_direction, delta_labels):
    if df.empty:
        st.warning(f"'{title}' 데이터를 표시할 수 없습니다.")
        return

    period_map = {"6m": 180, "1y": 365, "5y": 1825, "전체": None}
    if period_map[selected_period]:
        start_date = df["Date"].max() - pd.Timedelta(days=period_map[selected_period])
        plot_df = df[df["Date"] >= start_date]
    else:
        plot_df = df

    delta_html_list = []
    for delta_period, delta_label in zip(delta_periods, delta_labels):
        delta_html = calculate_delta_html(df, column_name, delta_period, delta_direction, delta_label)
        if delta_html:
            delta_html_list.append(delta_html)

    full_title = f"{title}" + "".join(delta_html_list)

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


# --- 4. Streamlit UI 구성 ---
st.markdown("<h1>📊 미래에셋 경제 주체별 변화 모니터</h1>", unsafe_allow_html=True)

period_opts = ["6m", "1y", "5y", "전체"]
selected_period = st.radio(
    "차트 기간 선택", period_opts, index=1, horizontal=True, key="global_period"
)

# [수정] fred_series_info에 단위 및 제목 개선 및 CPI 업데이트
# delta_period와 delta_label을 리스트로 변경하여 여러 기간을 표시할 수 있게 함
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

    st.markdown("<h3 style='font-size:1rem; font-weight:600; margin-top:1.2rem;'>주요 스테이블코인 시가총액</h3>", unsafe_allow_html=True)
    df_sc = get_stablecoin_data()
    if not df_sc.empty:
        total_market_cap = df_sc['market_cap'].sum()
        fig_sc = px.bar(df_sc, x='name', y='market_cap', text='market_cap', height=300, title=f"Total: ${total_market_cap:,.0f}")
        fig_sc.update_traces(texttemplate='$%{y:.2s}', textposition='outside')
        fig_sc.update_layout(margin=dict(t=40, b=20), yaxis_title=None, xaxis_title=None, title_font_size=16)
        st.plotly_chart(fig_sc, use_container_width=True)
        st.markdown(f"<div class='chart-date-info'>최근 데이터: <b>실시간</b> | 출처: <b>CoinGecko</b></div>", unsafe_allow_html=True)

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