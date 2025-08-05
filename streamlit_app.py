import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# 사용자 제공 FRED API 키
FRED_API_KEY = st.secrets["FRED_API_KEY"]

# FRED에서 시계열 데이터 가져오기 함수
def get_fred_series(series_id, label):
    url = f"https://api.stlouisfed.org/fred/series/observations"
    params = {
        'series_id': series_id,
        'api_key': FRED_API_KEY,
        'file_type': 'json'
    }
    r = requests.get(url, params=params)
    if r.status_code == 200:
        obs = r.json()['observations']
        df = pd.DataFrame(obs)
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        return df[['date', 'value']].rename(columns={'date': 'Date', 'value': label})
    else:
        return pd.DataFrame()

# Streamlit 설정
st.set_page_config(page_title="디지털 자산 모니터링", layout="wide")
st.title("📊 디지털 자산 기반 거시 모니터링 대시보드")

st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    h1 { font-size: 1.5rem; }
    h2 { font-size: 1.3rem; }
    h3 { font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# 화면 구성 - 2행 2열
row1_col1, row1_col2 = st.columns(2)
row2_col1, row2_col2 = st.columns(2)

# 1행 1열 - 글로벌 유동성 및 금리
with row1_col1:
    st.header("🌐 글로벌 유동성 및 금리")

    ffr_df = get_fred_series("FEDFUNDS", "Fed Funds Rate")
    rrp_df = get_fred_series("RRPONTSYD", "RRP (B$)")
    m2_df = get_fred_series("M2SL", "M2 ($B)")

    if not ffr_df.empty:
        fig_ffr = px.line(ffr_df.tail(60), x="Date", y="Fed Funds Rate", title="Fed Funds Rate", markers=True)
        st.plotly_chart(fig_ffr, use_container_width=True)
    if not rrp_df.empty:
        fig_rrp = px.line(rrp_df.tail(60), x="Date", y="RRP (B$)", title="Reverse Repo 잔고", markers=True)
        st.plotly_chart(fig_rrp, use_container_width=True)
    if not m2_df.empty:
        fig_m2 = px.line(m2_df.tail(60), x="Date", y="M2 ($B)", title="M2 통화량", markers=True)
        st.plotly_chart(fig_m2, use_container_width=True)

# 1행 2열 - Stablecoin & RWA
with row1_col2:
    st.header("💵 Stablecoin 시총 & RWA TVL")

    coins = ['tether', 'usd-coin', 'dai']
    url = 'https://api.coingecko.com/api/v3/coins/markets'
    params = {'vs_currency': 'usd', 'ids': ','.join(coins)}
    resp = requests.get(url, params=params)

    if resp.status_code == 200:
        stable_data = pd.DataFrame(resp.json())
        stable_df = stable_data[['name', 'market_cap']]
        fig_stable = px.bar(stable_df, x='name', y='market_cap', title="Stablecoin 시가총액 (USD)", text_auto='.2s')
        st.plotly_chart(fig_stable, use_container_width=True)

    rwa_query = """
    {
      protocols {
        name
        tvlUsd
      }
    }
    """
    rwa_resp = requests.post('https://api.rwa.xyz/graphql', json={'query': rwa_query})
    if rwa_resp.status_code == 200:
        rwa_data = pd.DataFrame(rwa_resp.json()['data']['protocols'])
        rwa_data = rwa_data.sort_values(by='tvlUsd', ascending=False)
        fig_rwa = px.bar(rwa_data, x='name', y='tvlUsd', title="RWA 프로토콜 TVL (USD)", text_auto='.2s')
        st.plotly_chart(fig_rwa, use_container_width=True)

# 2행 1열 - 신용시장
with row2_col1:
    st.header("🏦 신용시장 (예시 데이터)")

    sloos = pd.DataFrame({"분기": ["Q1", "Q2", "Q3", "Q4", "Q1"],
                          "SLOOS Index": [30, 20, 15, 5, -10]})
    fig_sloos = px.bar(sloos, x="분기", y="SLOOS Index", title="은행 대출 태도")
    st.plotly_chart(fig_sloos, use_container_width=True)

    hy_ig = pd.DataFrame({"Date": pd.date_range(end=pd.Timestamp.today(), periods=5, freq='M'),
                          "스프레드 (%)": [3.2, 3.5, 4.0, 4.5, 4.3]})
    fig_spread = px.line(hy_ig, x="Date", y="스프레드 (%)", markers=True, title="HY / IG 스프레드")
    st.plotly_chart(fig_spread, use_container_width=True)

# 2행 2열 - 기업/가계
with row2_col2:
    st.header("🏠 기업 및 가계 (예시 데이터)")

    capex = pd.DataFrame({"연도": [2019, 2020, 2021, 2022, 2023],
                          "CapEx Index": [100, 95, 110, 120, 125]})
    fig_capex = px.bar(capex, x="연도", y="CapEx Index", title="기업 CapEx")
    st.plotly_chart(fig_capex, use_container_width=True)

    credit = pd.DataFrame({"월": pd.date_range(end=pd.Timestamp.today(), periods=5, freq='M'),
                           "Credit Used ($B)": [920, 935, 950, 970, 985]})
    fig_credit = px.line(credit, x="월", y="Credit Used ($B)", markers=True, title="가계 소비 신용")
    st.plotly_chart(fig_credit, use_container_width=True)

    defi_users = pd.DataFrame({"월": pd.date_range(end=pd.Timestamp.today(), periods=5, freq='M'),
                               "DeFi Users (M)": [5.0, 5.2, 5.5, 5.8, 6.1]})
    fig_defi = px.line(defi_users, x="월", y="DeFi Users (M)", markers=True, title="DeFi 사용자 수")
    st.plotly_chart(fig_defi, use_container_width=True)