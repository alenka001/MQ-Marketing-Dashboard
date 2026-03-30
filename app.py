import streamlit as st
import pandas as pd
import re
import warnings
import plotly.express as px
import plotly.graph_objects as go

warnings.filterwarnings('ignore')

# --- CONFIGURATION & BRANDING ---
st.set_page_config(page_title="Marketing Intelligence Dashboard", layout="wide", page_icon="📊")

# Custom CSS for a "Premium" look
st.markdown("""
    <style>
    .stMetric { 
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 12px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #f0f2f6;
    }
    [data-testid="stHeader"] { background-color: #000000; }
    .main { background-color: #f9fbff; }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITY FUNCTIONS ---
def clean_val(val):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': 
        return 0.0
    s = str(val).strip().replace('€', '').replace('%', '').replace('SEK', '')
    s = re.sub(r'[\s\xa0]+', '', s) 
    if ',' in s:
        if '.' in s: s = s.replace('.', '')
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return 0.0

# --- SIDEBAR: SETTINGS ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/analytics.png", width=80)
    st.title("Settings")
    client_name = st.text_input("Client/Brand Name", value="Zalando")
    ex_rate = st.number_input("Exchange Rate (EUR to SEK)", value=10.66)
    
    st.markdown("---")
    st.header("📂 Data Source")
    f_mkt = st.file_uploader("Upload ZMS SKU Report (CSV)", type="csv")
    
    st.markdown("---")
    show_sek = st.checkbox("Show SEK Values", value=False)
    currency_label = "kr" if show_sek else "€"
    multiplier = ex_rate if show_sek else 1.0

# --- MAIN DASHBOARD ---
st.title(f"📊 {client_name} Marketing Intelligence")

if f_mkt:
    # Auto-detect separator
    try:
        header_line = f_mkt.readline().decode('utf-8')
        f_mkt.seek(0)
        sep = ';' if ';' in header_line else ','
        df = pd.read_csv(f_mkt, sep=sep, engine='python', encoding='utf-8')
    except:
        f_mkt.seek(0)
        df = pd.read_csv(f_mkt, sep=sep, engine='python', encoding='ISO-8859-1')
    
    df.columns = [c.replace(' ', '') for c in df.columns]
    
    # Mapping columns
    m_cols = {'Spend': 'Budgetspent', 'GMV': 'GMV', 'Wish': 'Addtowishlist', 'Clicks': 'Clicks', 'Sold': 'Itemssold'}
    
    # Clean Year/Week
    df['Week'] = df['Week'].apply(clean_val).astype(int)
    df['Year'] = df['Year'].apply(clean_val).astype(int)
    
    for k, v in m_cols.items():
        if v in df.columns:
            df[k] = df[v].apply(clean_val)
        else:
            df[k] = 0.0

    # Determine Timeframes
    years = sorted(df['Year'].unique())
    curr_yr = years[-1]
    df_curr = df[df['Year'] == curr_yr]
    weeks = sorted(df_curr['Week'].unique())

    if len(weeks) >= 2:
        # Week Selectors
        col_w1, col_w2 = st.columns(2)
        cw_w = col_w1.selectbox("Current Week", options=reversed(weeks), index=0)
        lw_w = col_w2.selectbox("Previous Week", options=reversed(weeks), index=1)

        m_cw = df_curr[df_curr['Week'] == cw_w]
        m_lw = df_curr[df_curr['Week'] == lw_w]
        
        s_cw = m_cw[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold']].sum()
        s_lw = m_lw[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold']].sum()

        roas_cw = s_cw['GMV']/s_cw['Spend'] if s_cw['Spend'] > 0 else 0
        roas_lw = s_lw['GMV']/s_lw['Spend'] if s_lw['Spend'] > 0 else 0

        # --- SECTION 1: WEEKLY SUMMARY ---
        st.subheader(f"Week {cw_w} vs Week {lw_w} Performance")
        k1, k2, k3, k4, k5 = st.columns(5)
        
        k1.metric("Ad Spend", f"{currency_label}{s_cw['Spend']*multiplier:,.0f}", 
                  delta=f"{(s_cw['Spend']-s_lw['Spend'])*multiplier:,.0f}", delta_color="inverse")
        k2.metric("Total GMV", f"{currency_label}{s_cw['GMV']*multiplier:,.0f}", 
                  delta=f"{(s_cw['GMV']-s_lw['GMV'])*multiplier:,.0f}")
        k3.metric("ROAS", f"{roas_cw:.2f}x", delta=f"{roas_cw-roas_lw:.2f}")
        k4.metric("Wishlists", f"{s_cw['Wish']:,.0f}", delta=f"{s_cw['Wish']-s_lw['Wish']:,.0f}")
        cvr_cw = (s_cw['Sold']/s_cw['Clicks'] if s_cw['Clicks']>0 else 0)
        k5.metric("CVR", f"{cvr_cw:.1%}")

        # --- SECTION 2: TREND ---
        st.markdown("---")
        trend_data = df_curr.groupby('Week')[['Spend', 'GMV']].sum().reset_index()
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(x=trend_data['Week'], y=trend_data['Spend'], name="Spend", line=dict(color='#ff4b4b')))
        fig_trend.add_trace(go.Bar(x=trend_data['Week'], y=trend_data['GMV'], name="GMV", opacity=0.3, marker_color='#0068c9'))
        fig_trend.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig_trend, use_container_width=True)

        # --- SECTION 3: YoY CAMPAIGN ---
        st.markdown("---")
        st.subheader("📣 Campaign Analytics (YoY Compare)")
        if len(years) >= 2:
            last_yr = years[-2]
            cw_camp = df[df['Year'] == curr_yr].groupby('ZMSCampaign')[['Spend', 'GMV']].sum().reset_index()
            ly_camp = df[df['Year'] == last_yr].groupby('ZMSCampaign')[['Spend', 'GMV']].sum().reset_index()
            m_comp = cw_camp.merge(ly_camp, on='ZMSCampaign', how='left', suffixes=('_CW', '_LY')).fillna(0)
            
            m_comp['Spend YoY %'] = (m_comp['Spend_CW'] - m_comp['Spend_LY']) / m_comp['Spend_LY'].replace(0, 1)
            m_comp['GMV YoY %'] = (m_comp['GMV_CW'] - m_comp['GMV_LY']) / m_comp['GMV_LY'].replace(0, 1)
            m_comp['ROAS'] = m_comp['GMV_CW'] / m_comp['Spend_CW'].replace(0, 1)
            
            # Apply multiplier for display
            disp_df = m_comp.copy()
            disp_df['Spend_CW'] *= multiplier
            disp_df['GMV_CW'] *= multiplier

            st.dataframe(
                disp_df[['ZMSCampaign', 'Spend_CW', 'Spend YoY %', 'GMV_CW', 'GMV YoY %', 'ROAS']].sort_values('Spend_CW', ascending=False),
                column_config={
                    "Spend_CW": st.column_config.NumberColumn(f"Spend {currency_label}", format=f"{currency_label}%.0f"),
                    "Spend YoY %": st.column_config.NumberColumn("Spend Δ LY", format="%.1f%%"),
                    "GMV_CW": st.column_config.NumberColumn(f"GMV {currency_label}", format=f"{currency_label}%.0f"),
                    "GMV YoY %": st.column_config.NumberColumn("GMV Δ LY", format="%.1f%%"),
                    "ROAS": st.column_config.NumberColumn("ROAS", format="%.2fx")
                },
                hide_index=True, use_container_width=True
            )
        else:
            st.warning("Only one year detected in file. Upload multi-year data for YoY comparison.")
    else:
        st.error("Insufficient week data for comparison.")
else:
    st.title("📊 Marketplace Marketing Intelligence")
    st.info("👈 Upload your ZMS CSV file in the sidebar to begin.")
