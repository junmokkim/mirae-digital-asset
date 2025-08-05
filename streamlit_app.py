import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# Page settings
st.set_page_config(page_title="디지털 자산 모니터링 대시보드", layout="wide")
st.title("📊 디지털 자산 기반 거시 모니터링 대시보드")

# Tabs for panels
tab1, tab2, tab3, tab4 = st.tabs([
    "1️⃣ 글로벌 유동성 & 금리", 
    "2️⃣ Stablecoin & RWA", 
    "3️⃣ 신용시장", 
    "4️⃣ 기업 & 가계"])

# Tab 1: 글로벌 유동성/금리
with tab1:
    st.header("🌐 글로벌 유동성 및 금리 흐름")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("• Fed Funds Rate (예시)")
        ffr = pd.DataFrame({"Date": pd.date_range(end=pd.Timestamp.today(), periods=5, freq='M'),
                            "FFR": [5.25, 5.25, 5.5, 5.5, 5.25]})
        fig1 = px.line(ffr, x="Date", y="FFR", markers=True)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.subheader("• Reverse Repo (예시)")
        rrp = pd.DataFrame({"Date": pd.date_range(end=pd.Timestamp.today(), periods=5, freq='M'),
                            "RRP (T$)": [2.3, 2.1, 1.9, 1.5, 1.1]})
        fig2 = px.line(rrp, x="Date", y="RRP (T$)", markers=True)
        st.plotly_chart(fig2, use_container_width=True)

    with col3:
        st.subheader("• M2 통화량 (예시)")
        m2 = pd.DataFrame({"Date": pd.date_range(end=pd.Timestamp.today(), periods=5, freq='M'),
                           "M2 ($T)": [21.5, 21.6, 21.8, 22.0, 22.2]})
        fig3 = px.line(m2, x="Date", y="M2 ($T)", markers=True)
        st.plotly_chart(fig3, use_container_width=True)

# Tab 2: Stablecoin & RWA
with tab2:
    st.header("💵 Stablecoin 시총 & RWA TVL")

    # Stablecoin 시총 (CoinGecko)
    st.subheader("• 주요 Stablecoin 시가총액")
    coins = ['tether', 'usd-coin', 'dai']
    url = 'https://api.coingecko.com/api/v3/coins/markets'
    params = {'vs_currency': 'usd', 'ids': ','.join(coins)}
    resp = requests.get(url, params=params)

    if resp.status_code == 200:
        stable_data = pd.DataFrame(resp.json())
        stable_df = stable_data[['name', 'market_cap', 'current_price']]
        stable_df.columns = ['이름', '시가총액 (USD)', '현재가 (USD)']
        stable_df['시가총액 (USD)'] = stable_df['시가총액 (USD)'].apply(lambda x: f"${x:,.0f}")
        st.table(stable_df)
    else:
        st.error("CoinGecko API 호출 실패")

    # RWA TVL (rwa.xyz)
    st.subheader("• RWA 프로토콜별 TVL")
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
    else:
        st.error("rwa.xyz API 호출 실패")

# Tab 3: 신용시장
with tab3:
    st.header("🏦 신용시장 환경")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("• 은행 대출 태도 (예시)")
        sloos = pd.DataFrame({"분기": ["Q1", "Q2", "Q3", "Q4", "Q1"],
                              "SLOOS Index": [30, 20, 15, 5, -10]})
        fig_sloos = px.bar(sloos, x="분기", y="SLOOS Index")
        st.plotly_chart(fig_sloos, use_container_width=True)

    with col2:
        st.subheader("• HY / IG 스프레드 (예시)")
        hy_ig = pd.DataFrame({"Date": pd.date_range(end=pd.Timestamp.today(), periods=5, freq='M'),
                              "스프레드 (%)": [3.2, 3.5, 4.0, 4.5, 4.3]})
        fig_spread = px.line(hy_ig, x="Date", y="스프레드 (%)", markers=True)
        st.plotly_chart(fig_spread, use_container_width=True)

# Tab 4: 기업/가계
with tab4:
    st.header("🏠 기업 및 가계 활동")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("• 기업 CapEx (예시)")
        capex = pd.DataFrame({"연도": [2019, 2020, 2021, 2022, 2023],
                              "CapEx Index": [100, 95, 110, 120, 125]})
        fig_capex = px.bar(capex, x="연도", y="CapEx Index")
        st.plotly_chart(fig_capex, use_container_width=True)

    with col2:
        st.subheader("• 가계 소비 신용 (예시)")
        credit = pd.DataFrame({"월": pd.date_range(end=pd.Timestamp.today(), periods=5, freq='M'),
                               "Credit Used ($B)": [920, 935, 950, 970, 985]})
        fig_credit = px.line(credit, x="월", y="Credit Used ($B)", markers=True)
        st.plotly_chart(fig_credit, use_container_width=True)

    with col3:
        st.subheader("• DeFi 사용자 수 (예시)")
        defi_users = pd.DataFrame({"월": pd.date_range(end=pd.Timestamp.today(), periods=5, freq='M'),
                                   "DeFi Users (M)": [5.0, 5.2, 5.5, 5.8, 6.1]})
        fig_defi = px.line(defi_users, x="월", y="DeFi Users (M)", markers=True)
        st.plotly_chart(fig_defi, use_container_width=True)
