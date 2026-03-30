import streamlit as st
import pandas as pd
import re
import warnings
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

# --- CONFIGURATION & BRANDING ---
st.set_page_config(page_title="Marketing Intelligence Dashboard", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e6e9ef; }
    [data-testid="stHeader"] { background-color: #000000; }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITY FUNCTIONS ---
def clean_val(val):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': return 0.0
    s = str(val).strip().replace('€', '').replace('%', '').replace('SEK', '')
    s = re.sub(r'[\s\xa0]+', '', s) 
    if ',' in s:
        if '.' in s: s = s.replace('.', '')
        s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

def get_delta_pct(current, previous):
    if previous == 0: return 0.0
    return (current - previous) / previous

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/analytics.png", width=60)
    st.title("Control Panel")
    client_name = st.text_input("Brand", value="Zalando")
    ex_rate = st.number_input("EUR to SEK", value=10.66)
    f_mkt = st.file_uploader("Upload ZMS Report (CSV)", type="csv")
    show_sek = st.checkbox("Show SEK", value=False)
    
    currency_label = "kr" if show_sek else "€"
    multiplier = ex_rate if show_sek else 1.0

# --- DATA PROCESSING ---
if f_mkt:
    try:
        df = pd.read_csv(f_mkt, sep=None, engine='python', encoding='utf-8')
    except:
        f_mkt.seek(0)
        df = pd.read_csv(f_mkt, sep=None, engine='python', encoding='ISO-8859-1')
    
    df.columns = [c.replace(' ', '') for c in df.columns]
    
    # Advanced Column Mapping
    mapping = {
        'Spend': 'Budgetspent', 'GMV': 'GMV', 'Wish': 'Addtowishlist', 
        'Clicks': 'Clicks', 'Sold': 'Itemssold', 'Impressions': 'Impressions',
        'ConfigSKU': 'ArticleSKU', 'Campaign': 'ZMSCampaign'
    }
    
    df['Week'] = df['Week'].apply(clean_val).astype(int)
    df['Year'] = df['Year'].apply(clean_val).astype(int)
    
    for k, v in mapping.items():
        if v in df.columns:
            if k in ['ConfigSKU', 'Campaign']: df[k] = df[v].astype(str)
            else: df[k] = df[v].apply(clean_val)
        else:
            df[k] = 0.0 if k not in ['ConfigSKU', 'Campaign'] else "Unknown"

    # --- TIME LOGIC ---
    years = sorted(df['Year'].unique())
    curr_yr = years[-1]
    prev_yr = years[-2] if len(years) > 1 else None
    
    weeks = sorted(df[df['Year'] == curr_yr]['Week'].unique())
    cw = weeks[-1]
    lw = weeks[-2] if len(weeks) > 1 else None
    llw = weeks[-3] if len(weeks) > 2 else None

    # --- METRIC CALCULATION ---
    def get_stats(year, week):
        temp = df[(df['Year'] == year) & (df['Week'] == week)]
        res = temp[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold', 'Impressions']].sum()
        res['ROAS'] = res['GMV'] / res['Spend'] if res['Spend'] > 0 else 0
        return res

    s_cw = get_stats(curr_yr, cw)
    s_lw = get_stats(curr_yr, lw) if lw else s_cw * 0
    s_ly = get_stats(prev_yr, cw) if prev_yr else s_cw * 0
    s_llw = get_stats(curr_yr, llw) if llw else s_lw * 0

    # --- MAIN UI ---
    st.title(f"📊 {client_name} Marketing Intelligence")
    
    # 1. SUMMARY TILES
    st.subheader(f"Performance Summary: Week {cw}")
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.metric("Ad Spend", f"{currency_label}{s_cw['Spend']*multiplier:,.0f}", 
                  delta=f"WoW: {get_delta_pct(s_cw['Spend'], s_lw['Spend']):.1%} | LY: {get_delta_pct(s_cw['Spend'], s_ly['Spend']):.1%}")
    with m2:
        st.metric("Total GMV", f"{currency_label}{s_cw['GMV']*multiplier:,.0f}", 
                  delta=f"WoW: {get_delta_pct(s_cw['GMV'], s_lw['GMV']):.1%} | LY: {get_delta_pct(s_cw['GMV'], s_ly['GMV']):.1%}")
    with m3:
        st.metric("ROAS", f"{s_cw['ROAS']:.2f}x", 
                  delta=f"WoW: {get_delta_pct(s_cw['ROAS'], s_lw['ROAS']):.1%} | LY: {get_delta_pct(s_cw['ROAS'], s_ly['ROAS']):.1%}")
    with m4:
        st.metric("Impressions", f"{s_cw['Impressions']:,.0f}", 
                  delta=f"WoW: {get_delta_pct(s_cw['Impressions'], s_lw['Impressions']):.1%} | LY: {get_delta_pct(s_cw['Impressions'], s_ly['Impressions']):.1%}")

    # 2. TREND CHART (DUAL AXIS)
    st.markdown("---")
    trend = df[df['Year'] == curr_yr].groupby('Week').agg({'Spend':'sum', 'GMV':'sum'}).reset_index()
    trend['ROAS'] = trend['GMV'] / trend['Spend']
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=trend['Week'], y=trend['Spend'], name="Spend", marker_color='#ff4b4b'), secondary_y=False)
    fig.add_trace(go.Bar(x=trend['Week'], y=trend['GMV'], name="GMV", marker_color='#0068c9', opacity=0.6), secondary_y=False)
    fig.add_trace(go.Scatter(x=trend['Week'], y=trend['ROAS'], name="ROAS", line=dict(color='#2ecc71', width=3)), secondary_y=True)
    
    fig.update_layout(title="Weekly Spend, GMV & ROAS Trend", barmode='group', height=400)
    st.plotly_chart(fig, use_container_width=True)

    # 3. CAMPAIGN ANALYTICS (WoW & YoY)
    st.markdown("---")
    st.subheader("📣 Campaign Analytics")

    def prep_comp(group_col):
        c_data = df[(df['Year']==curr_yr) & (df['Week']==cw)].groupby(group_col)[['Spend','GMV']].sum()
        l_data = df[(df['Year']==curr_yr) & (df['Week']==lw)].groupby(group_col)[['Spend','GMV']].sum()
        ll_data = df[(df['Year']==curr_yr) & (df['Week']==llw)].groupby(group_col)[['Spend','GMV']].sum()
        y_data = df[(df['Year']==prev_yr) & (df['Week']==cw)].groupby(group_col)[['Spend','GMV']].sum() if prev_yr else pd.DataFrame()

        final = c_data.join(l_data, rsuffix='_LW').join(ll_data, rsuffix='_LLW').join(y_data, rsuffix='_LY').fillna(0)
        
        # Calculations
        final['Spend WoW%'] = (final['Spend'] - final['Spend_LW']) / final['Spend_LW'].replace(0,1)
        final['Spend LY%'] = (final['Spend'] - final['Spend_LY']) / final['Spend_LY'].replace(0,1)
        final['GMV WoW%'] = (final['GMV'] - final['GMV_LW']) / final['GMV_LW'].replace(0,1)
        final['GMV LY%'] = (final['GMV'] - final['GMV_LY']) / final['GMV_LY'].replace(0,1)
        
        final['ROAS'] = final['GMV'] / final['Spend'].replace(0,1)
        final['ROAS_LW'] = final['GMV_LW'] / final['Spend_LW'].replace(0,1)
        final['ROAS Δ'] = final['ROAS'] - final['ROAS_LW']
        return final.reset_index()

    camp_df = prep_comp('Campaign')
    st.dataframe(camp_df[['Campaign', 'Spend', 'Spend WoW%', 'Spend LY%', 'GMV', 'GMV WoW%', 'GMV LY%', 'ROAS', 'ROAS Δ']], 
                 column_config={
                     "Spend": st.column_config.NumberColumn(f"Spend {currency_label}"),
                     "Spend WoW%": st.column_config.NumberColumn("vs LW %", format="%.1f%%"),
                     "Spend LY%": st.column_config.NumberColumn("vs LY %", format="%.1f%%"),
                     "GMV WoW%": st.column_config.NumberColumn("GMV vs LW %", format="%.1f%%"),
                     "ROAS Δ": st.column_config.NumberColumn("ROAS vs LW", format="%.2f")
                 }, hide_index=True, use_container_width=True)

    # 4. ARTICLE ANALYTICS
    st.markdown("---")
    st.subheader("📦 Article SKU Performance (Last Week)")
    art_df = df[(df['Year']==curr_yr) & (df['Week']==cw)].groupby('ConfigSKU').agg({
        'GMV': 'sum', 'Spend': 'sum', 'Clicks': 'sum', 'Sold': 'sum', 'Wish': 'sum'
    }).reset_index()
    
    art_df['ROAS'] = art_df['GMV'] / art_df['Spend'].replace(0,1)
    art_df['CVR'] = art_df['Sold'] / art_df['Clicks'].replace(0,1)
    
    st.dataframe(art_df[['ConfigSKU', 'ROAS', 'Clicks', 'CVR', 'Wish']].sort_values('ROAS', ascending=False),
                 column_config={
                     "ROAS": st.column_config.NumberColumn("ROAS", format="%.2fx"),
                     "CVR": st.column_config.NumberColumn("CVR", format="%.1%"),
                     "Wish": st.column_config.NumberColumn("Wishlists")
                 }, hide_index=True, use_container_width=True)

else:
    st.info("👈 Please upload the ZMS CSV file to generate the Intelligence Report.")
