import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import openai

# ----- 환경설정 -----
FRED_API_KEY = '2f8671e0ca92ead96539311a2fb0d1fb'
OPENAI_API_KEY = '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'
openai.api_key = OPENAI_API_KEY

# ----- FRED 시계열 -----
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
        df = df[['date', 'value']].rename(columns={'date': 'Date', 'value': label})
        df = df.sort_values('Date')
        return df
    else:
        return pd.DataFrame()

def calc_change(df, label, days=30):
    if len(df) < days:
        return None
    latest = df.iloc[-1][label]
    prior = df.iloc[-days][label]
    if pd.isna(prior) or prior == 0:
        return None
    return ((latest - prior) / prior) * 100

def color_delta(pct, threshold=3):
    if pct is None:
        return ""
    color = "green" if pct >= 0 else "red"
    strong = abs(pct) >= threshold
    weight = "bold" if strong else "normal"
    icon = "🔺" if pct > 0 else ("🔻" if pct < 0 else "")
    return f"<span style='color:{color}; font-weight:{weight}'>{icon}{pct:+.2f}%</span>"

# ----- Streamlit 설정 -----
st.set_page_config(page_title="디지털 자산 모니터링", layout="wide")
st.markdown("""
<style>
    .block-container {padding-top:0.5rem;padding-bottom:0.5rem;}
    h1,h2,h3,.stMetricLabel{font-size:0.9rem !important;}
</style>
""", unsafe_allow_html=True)

st.title("📊 글로벌 RWA 및 Stablecoin 시장 모니터링")

lookback = st.slider("🔍 비교 기간 (일)", min_value=7, max_value=90, value=30, step=7)

# ----- 실시간 주요 지표 -----
rwa_total = 24.81
rwa_change_pct = -0.33
holders = 340688
holders_change_pct = 21.42
stablecoin_total = 257.38
stablecoin_change_pct = 4.55

rrp_df = get_fred_series("RRPONTSYD", "RRP")
rrp_change = calc_change(rrp_df, "RRP", lookback)
rrp_latest = rrp_df.iloc[-1]["RRP"] if not rrp_df.empty else None

# 신용지표
sloos_df = get_fred_series('DRTSCILM','SLOOS')
sloos_change = calc_change(sloos_df,'SLOOS',lookback)
credit_df = get_fred_series('TOTALSL','ConsumerCredit')
credit_change = calc_change(credit_df,'ConsumerCredit',lookback)
ig_spread_df = get_fred_series('BAA10Y','IGSpread')
ig_change = calc_change(ig_spread_df,'IGSpread',lookback)
hy_spread_df = get_fred_series('BAMLH0A0HYM2','HYSpread')
hy_change = calc_change(hy_spread_df,'HYSpread',lookback)

# ----- Executive Summary 생성 -----
summary_context = f'''
- Total RWA Onchain: ${rwa_total:.2f}B ({rwa_change_pct:+.2f}%)
- Total Asset Holders: {holders:,} ({holders_change_pct:+.2f}%)
- Total Stablecoin Value: ${stablecoin_total:.2f}B ({stablecoin_change_pct:+.2f}%)
- Fed RRP: {rrp_latest/1000:.2f}T ({rrp_change:+.2f}%)
- SLOOS: {sloos_change:+.2f}%
- Consumer Credit: {credit_change:+.2f}%
- IG Spread: {ig_change:+.2f}%
- HY Spread: {hy_change:+.2f}%
'''

def get_gpt_summary(prompt_text):
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a global asset allocation strategist. Write a 3-line, executive-level summary in Korean for the digital asset and credit markets dashboard. Be concise, evidence-based, and objective."},
            {"role": "user", "content": prompt_text}
        ],
        temperature=0.2,
        max_tokens=180
    )
    return response['choices'][0]['message']['content'].strip()

with st.spinner("AI Executive Summary 작성 중..."):
    try:
        executive_summary = get_gpt_summary(summary_context)
    except Exception as e:
        executive_summary = "⚠️ AI executive summary 기능이 일시적으로 불가합니다."

st.info(f"**📝 Executive Summary:**\n{executive_summary}")

# ----- 메트릭 카드 -----
col1, col2, col3, col4 = st.columns(4)
col1.metric("🧱 Total RWA Onchain", f"${rwa_total:.2f}B", f"{rwa_change_pct:+.2f}%")
col2.metric("👤 Total Asset Holders", f"{holders:,}", f"↑ {holders_change_pct:.2f}%")
col3.metric("🪙 Total Stablecoin Value", f"${stablecoin_total:.2f}B", f"+{stablecoin_change_pct:.2f}%")
if rrp_latest is not None:
    col4.metric("🏦 Fed RRP 잔고", f"${rrp_latest/1000:.2f}T", f"{rrp_change:+.2f}%")
else:
    col4.metric("🏦 Fed RRP 잔고", "N/A", "")

# ----- Pie chart -----
st.markdown("### 🥧 Total RWA Breakdown (08/04/2025)")
pie = pd.DataFrame({
    'category':['Private Credit','US Treasury Debt','Commodities','Institutional Funds'],
    'value':[14.7,6.8,1.8,0.8211]
})
fig = px.pie(pie, names='category', values='value', hole=0.4)
fig.update_traces(textinfo='label+percent')
fig.update_layout(margin=dict(t=20,b=20,l=20,r=20), height=280)
st.plotly_chart(fig, use_container_width=True)

# ----- Stablecoin bar -----
st.markdown("### 🪙 주요 Stablecoin 시가총액 (CoinGecko)")
coins = ['tether','usd-coin','dai']
resp = requests.get('https://api.coingecko.com/api/v3/coins/markets', params={'vs_currency':'usd','ids':','.join(coins)})
if resp.ok:
    df_sc = pd.DataFrame(resp.json())[['name','market_cap']]
    fig_sc = px.bar(df_sc, x='name', y='market_cap', text='market_cap', height=250)
    fig_sc.update_traces(texttemplate='$%{value:.2s}',textposition='outside')
    fig_sc.update_layout(margin=dict(t=10,b=20), yaxis_title=None)
    st.plotly_chart(fig_sc,use_container_width=True)
else:
    st.error("CoinGecko 호출 실패")

st.markdown("---")
st.subheader("📉 신용시장 & 가계 신용 (FRED, 변화율 색상/경고)")

cols = st.columns(2)

with cols[0]:
    ch1 = sloos_change
    st.markdown(f"**SLOOS 대출기준 변화율:** {color_delta(ch1)}", unsafe_allow_html=True)
    fig1 = px.line(sloos_df.tail(60),x='Date',y='SLOOS',height=250)
    st.plotly_chart(fig1, use_container_width=True)

    ch2 = credit_change
    st.markdown(f"**가계 소비신용 변화율:** {color_delta(ch2)}", unsafe_allow_html=True)
    fig2 = px.line(credit_df.tail(60),x='Date',y='ConsumerCredit',height=250)
    st.plotly_chart(fig2, use_container_width=True)

with cols[1]:
    ch3 = ig_change
    st.markdown(f"**IG 스프레드 변화율:** {color_delta(ch3)}", unsafe_allow_html=True)
    fig3 = px.line(ig_spread_df.tail(60),x='Date',y='IGSpread',height=250)
    st.plotly_chart(fig3, use_container_width=True)

    ch4 = hy_change
    st.markdown(f"**HY 스프레드 변화율:** {color_delta(ch4)}", unsafe_allow_html=True)
    fig4 = px.line(hy_spread_df.tail(60),x='Date',y='HYSpread',height=250)
    st.plotly_chart(fig4, use_container_width=True)