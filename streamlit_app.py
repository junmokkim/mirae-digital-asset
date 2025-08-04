import streamlit as st
import pandas as pd

st.set_page_config(page_title="Stablecoin & RWA Dashboard", layout="wide")

st.title("💹 디지털 자산 모니터링 대시보드")

# 1. 중앙은행/유동성 섹션
st.header("1️⃣ 글로벌 유동성 & 금리")
col1, col2 = st.columns(2)
with col1:
    st.subheader("금리 (FFR)")
    # Placeholder (데이터 나중에 연결)
    st.line_chart(pd.DataFrame({"FFR":[5.25,5.25,5.5]}))
with col2:
    st.subheader("M2 통화량")
    st.line_chart(pd.DataFrame({"M2":[21.5, 21.7, 21.9]}))

# 2. Stablecoin & RWA 섹션
st.header("2️⃣ Stablecoin & RWA")
st.line_chart(pd.DataFrame({"Stablecoin_MarketCap":[130, 132, 135]}))

st.info("데이터는 CoinMetrics, DefiLlama, FRED 등 API 연결 예정")