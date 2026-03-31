import streamlit as st
import pandas as pd
import re
import warnings
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

# --- CONFIGURATION & BRANDING ---
st.set_page_config(page_title="Strategic Marketing Intelligence", layout="wide", page_icon="📊")

# Custom CSS for UI (Preserved)
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e6e9ef; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stHeader"] { background-color: #000000; }
    .commentary-box { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #000000; margin-top: 10px; margin-bottom: 20px; height: 100%; }
    .main { background-color: #f9fbff; }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITY FUNCTIONS (Enhanced for better data reading) ---
def clean_val(val):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': return 0.0
    # Remove symbols and ALL types of spaces (including spaces inside numbers like 28 846)
    s = str(val).strip().replace('€', '').replace('%', '').replace('SEK', '')
    s = re.sub(r'[\s\xa0]+', '', s) 
    # Handle European decimal format (comma to dot)
    if ',' in s:
        if '.' in s: s = s.replace('.', '') # Remove thousand separator if dot
        s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

def get_delta_pct(current, previous):
    if previous == 0: return 0.0
    return (current - previous) / previous

# --- SIDEBAR: SETTINGS & UPLOADS ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/analytics.png", width=60)
    st.title("Settings")
    client_name = st.text_input("Brand", value="MQ Marqet")
    ex_rate = st.number_input("EUR to SEK", value=10.66)
    
    st.markdown("---")
    st.header("📅 Time Granularity")
    # New: Toggle between Weekly and Monthly
    time_grain = st.radio("View by:", ["Week", "Month"])
    
    st.markdown("---")
    st.header("📂 Data Source")
    f_mkt = st.file_uploader("1. ZMS Market Report (CSV)", type="csv")
    f_inv = st.file_uploader("2. Inventory SKU Report (CSV)", type="csv")
    
    st.markdown("---")
    show_sek = st.checkbox("Show SEK Values", value=False)
    currency_label = "kr" if show_sek else "€"
    multiplier = ex_rate if show_sek else 1.0

# --- MAIN DASHBOARD LOGIC ---
if f_mkt:
    # 1. LOAD MARKET DATA
    try:
        df = pd.read_csv(f_mkt, sep=';', engine='python', encoding='utf-8')
    except:
        f_mkt.seek(0)
        df = pd.read_csv(f_mkt, sep=';', engine='python', encoding='ISO-8859-1')
    
    df.columns = [c.strip() for c in df.columns]
    
    # Mapping (Preserved & Enhanced)
    m_cols = {
        'Spend': 'Budget spent', 'GMV': 'GMV', 'Wish': 'Add to wishlist', 
        'Clicks': 'Clicks', 'Sold': 'Items sold', 'Impressions': 'Viewable ad impressions'
    }
    for k, v in m_cols.items():
        if v in df.columns: df[k] = df[v].apply(clean_val)
        else: df[k] = 0.0

    # 2. LOAD INVENTORY DATA & PIVOT STOCK (Aggressive Match Version) - Preserved
    inv_map = {}
    stock_map = {}
    if f_inv:
        try:
            df_inv = pd.read_csv(f_inv, sep=';', engine='python', encoding='utf-8')
        except:
            f_inv.seek(0)
            df_inv = pd.read_csv(f_inv, sep=';', engine='python', encoding='ISO-8859-1')
        
        df_inv.columns = [c.strip().lower() for c in df_inv.columns]
        inv_sku_col = next((c for c in df_inv.columns if 'zalando_article_variant' in c), None)
        name_col = next((c for c in df_inv.columns if 'article_name' in c), None)
        
        if inv_sku_col and name_col:
            df_inv[inv_sku_col] = df_inv[inv_sku_col].astype(str).str.strip().str.upper()
            df_inv['zfs_clean'] = df_inv.get('sellable_zfs_stock', 0).apply(clean_val)
            df_inv['pf_clean'] = df_inv.get('sellable_pf_stock', 0).apply(clean_val)
            
            inv_pivoted = df_inv.groupby(inv_sku_col).agg({
                name_col: 'first',
                'zfs_clean': 'sum',
                'pf_clean': 'sum'
            }).reset_index()
            
            inv_map = inv_pivoted.set_index(inv_sku_col)[name_col].to_dict()
            stock_map = inv_pivoted.set_index(inv_sku_col)[['zfs_clean', 'pf_clean']].sum(axis=1).to_dict()
            
            df['Config SKU Match'] = df['Config SKU'].astype(str).str.strip().str.upper()
            df['ArticleName'] = df['Config SKU Match'].map(inv_map).fillna(df['Config SKU'])
            df['TotalStock'] = df['Config SKU Match'].map(stock_map).fillna(0)
        else:
            df['ArticleName'] = df['Config SKU']
            df['TotalStock'] = 0
    else:
        df['ArticleName'] = df['Config SKU']
        df['TotalStock'] = 0

    # --- TOP FILTERS ---
    st.title(f"📊 {client_name} Strategic Board")
    
    years = sorted(df['Year'].unique(), reverse=True)
    c1, c2, c3 = st.columns(3)
    sel_year = c1.selectbox("Filter Year", years, index=0)
    
    available_periods = sorted(df[df['Year'] == sel_year][time_grain].unique(), reverse=True)
    curr_p = c2.selectbox(f"Current {time_grain}", available_periods, index=0)
    last_p = c3.selectbox(f"Comparison {time_grain}", available_periods, index=min(1, len(available_periods)-1))

    # Sidebar: Gender and Market Filters
    with st.sidebar:
        st.markdown("---")
        st.header("🎯 Target Filters")
        all_markets = ["All Markets"] + sorted([str(x) for x in df['Market'].dropna().unique()])
        sel_market = st.selectbox("Market Selector", all_markets)
        all_genders = ["All Genders"] + sorted([str(x) for x in df['Gender'].dropna().unique() if str(x).lower() != 'undefined'])
        sel_gender = st.selectbox("Gender Selector", all_genders)

    # Apply Global Filtering
    df_f = df[df['Year'] == sel_year].copy()
    if sel_market != "All Markets":
        df_f = df_f[df_f['Market'] == sel_market]
    if sel_gender != "All Genders":
        df_f = df_f[df_f['Gender'] == sel_gender]

    # --- CALCULATIONS ---
    def get_period_stats(val):
        subset = df_f[df_f[time_grain] == val]
        stats = subset[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold', 'Impressions']].sum()
        stats['ROAS'] = stats['GMV'] / stats['Spend'] if stats['Spend'] > 0 else 0
        return stats

    s_cw = get_period_stats(curr_p)
    s_lw = get_period_stats(last_p)

    # --- UI SECTION 1: KPI TILES ---
    st.subheader(f"Performance Snapshot: {time_grain} {curr_p} vs {time_grain} {last_p}")
    k1, k2, k3, k4, k5 = st.columns(5)
    
    k1.metric("Ad Spend", f"{currency_label}{s_cw['Spend']*multiplier:,.0f}", 
              delta=f"{get_delta_pct(s_cw['Spend'], s_lw['Spend']):.1%}", delta_color="inverse")
    k2.metric("Total GMV", f"{currency_label}{s_cw['GMV']*multiplier:,.0f}", 
              delta=f"{get_delta_pct(s_cw['GMV'], s_lw['GMV']):.1%}")
    k3.metric("ROAS", f"{s_cw['ROAS']:.2f}x", 
              delta=f"{s_cw['ROAS'] - s_lw['ROAS']:.2f} pts")
    k4.metric("Wishlists", f"{s_cw['Wish']:,.0f}", 
              delta=f"{get_delta_pct(s_cw['Wish'], s_lw['Wish']):.1%}")
    k5.metric("CVR", f"{(s_cw['Sold']/s_cw['Clicks'] if s_cw['Clicks']>0 else 0):.1%}")

    # --- UI SECTION 2: VISUAL ANALYTICS (Restored the nice graph) ---
    st.markdown("---")
    row2_1, row2_2 = st.columns([2, 1])

    with row2_1:
        st.subheader("Marketing Efficiency Trend")
        trend_data = df_f.groupby(time_grain).agg({'Spend':'sum', 'GMV':'sum'}).reset_index()
        trend_data['ROAS'] = trend_data['GMV'] / trend_data['Spend']
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=trend_data[time_grain], y=trend_data['Spend']*multiplier, name="Spend", marker_color='#ff4b4b'), secondary_y=False)
        fig.add_trace(go.Bar(x=trend_data[time_grain], y=trend_data['GMV']*multiplier, name="GMV", marker_color='#0068c9', opacity=0.6), secondary_y=False)
        fig.add_trace(go.Scatter(x=trend_data[time_grain], y=trend_data['ROAS'], name="ROAS", line=dict(color='#2ecc71', width=3)), secondary_y=True)
        fig.update_layout(barmode='group', height=400, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

    with row2_2:
        st.subheader("Top Wishlisted Styles")
        wish_df = df_f[df_f[time_grain] == curr_p].groupby(['ArticleName', 'Config SKU'])['Wish'].sum().reset_index()
        wish_df = wish_df.sort_values('Wish', ascending=False).head(10)
        
        fig_wish = px.bar(
            wish_df, 
            y='ArticleName', 
            x='Wish', 
            orientation='h', 
            color_discrete_sequence=['#ffaa00'],
            labels={'ArticleName': 'Product Name', 'Wish': 'Wishlists'}
        )
        fig_wish.update_layout(height=400, margin=dict(l=0, r=0, t=20, b=0), yaxis={'categoryorder':'total ascending'}, showlegend=False)
        st.plotly_chart(fig_wish, use_container_width=True)

    # --- NEW: COPY SKU SECTION & CATEGORY ANALYSIS ---
    st.markdown("---")
    c_cat, c_sku = st.columns([1, 1])
    
    with c_cat:
        st.subheader("📁 Category Performance")
        cat_df = df_f[df_f[time_grain] == curr_p].groupby('Category').agg({'Spend':'sum', 'GMV':'sum'}).reset_index()
        cat_df['ROAS'] = cat_df['GMV'] / cat_df['Spend']
        cat_df['COS'] = (cat_df['Spend'] / cat_df['GMV']).fillna(0)
        st.dataframe(
            cat_df.sort_values('GMV', ascending=False),
            column_config={
                "Spend": st.column_config.NumberColumn(format=f"{currency_label}%.0f"),
                "GMV": st.column_config.NumberColumn(format=f"{currency_label}%.0f"),
                "ROAS": st.column_config.NumberColumn(format="%.2fx"),
                "COS": st.column_config.NumberColumn(format="%.1%"),
            }, hide_index=True, use_container_width=True
        )

    with c_sku:
        st.subheader("📋 Top Styles (Copy Config SKU)")
        # This makes it easy to copy the SKUs directly
        st.dataframe(wish_df[['Config SKU', 'ArticleName', 'Wish']], hide_index=True, use_container_width=True)

    # --- NEW: MARKET PERFORMANCE & SHARE ---
    st.markdown("---")
    st.subheader("🌍 Market Performance & GMV Share")
    m_data = df_f[df_f[time_grain] == curr_p].groupby('Market').agg({'Spend':'sum', 'GMV':'sum'}).reset_index()
    total_gmv_period = m_data['GMV'].sum()
    m_data['ROAS'] = m_data['GMV'] / m_data['Spend']
    m_data['COS'] = (m_data['Spend'] / m_data['GMV']).fillna(0)
    m_data['GMV Share %'] = (m_data['GMV'] / total_gmv_period).fillna(0)
    
    st.dataframe(
        m_data.sort_values('GMV', ascending=False),
        column_config={
            "Spend": st.column_config.NumberColumn(format=f"{currency_label}%.0f"),
            "GMV": st.column_config.NumberColumn(format=f"{currency_label}%.0f"),
            "ROAS": st.column_config.NumberColumn(format="%.2fx"),
            "COS": st.column_config.NumberColumn(format="%.1%"),
            "GMV Share %": st.column_config.ProgressColumn(format="%.1%", min_value=0, max_value=1)
        }, hide_index=True, use_container_width=True
    )

    # --- UI SECTION 3: CAMPAIGN & STOCK THREAT ---
    st.markdown("---")
    st.subheader("📣 Campaign Level Breakdown & Stock Threats")
    
    camp_cw = df_f[df_f[time_grain] == curr_p].groupby(['ZMS Campaign', 'Config SKU', 'ArticleName']).agg({
        'Spend':'sum', 'GMV':'sum', 'Wish':'sum', 'Sold':'sum', 'TotalStock':'max'
    }).reset_index()
    
    camp_cw['Stock Threat'] = camp_cw.apply(lambda x: "🚨 Sell Out Risk" if x['Sold'] >= x['TotalStock'] and x['TotalStock'] > 0 else ("✅ OK" if x['TotalStock'] > 0 else "❓ No Data"), axis=1)

    st.dataframe(
        camp_cw[['ZMS Campaign', 'ArticleName', 'Config SKU', 'Sold', 'TotalStock', 'Stock Threat', 'Spend', 'GMV', 'Wish']].sort_values('Sold', ascending=False),
        column_config={
            "Spend": st.column_config.NumberColumn(f"Spend {currency_label}", format=f"{currency_label}%.0f"),
            "GMV": st.column_config.NumberColumn(f"GMV {currency_label}", format=f"{currency_label}%.0f"),
            "Sold": f"Sold ({time_grain})",
            "TotalStock": "Style Stock Level"
        }, hide_index=True, use_container_width=True
    )

else:
    st.title("📊 Strategic Marketplace Intelligence")
    st.info("👈 Please upload the **ZMS Market Report** and **Inventory Report** in the sidebar to populate the dashboard.")
