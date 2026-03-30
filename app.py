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

# --- UTILITY FUNCTIONS (Preserved) ---
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

# --- SIDEBAR: SETTINGS & UPLOADS ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/analytics.png", width=60)
    st.title("Settings")
    client_name = st.text_input("Brand", value="MQ Marqet")
    ex_rate = st.number_input("EUR to SEK", value=10.66)
    
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
    
    # Mapping (Preserved)
    m_cols = {
        'Spend': 'Budget spent', 'GMV': 'GMV', 'Wish': 'Add to wishlist', 
        'Clicks': 'Clicks', 'Sold': 'Items sold', 'Impressions': 'Viewable ad impressions'
    }
    for k, v in m_cols.items():
        if v in df.columns: df[k] = df[v].apply(clean_val)
        else: df[k] = 0.0

    # 2. LOAD INVENTORY DATA & PIVOT STOCK (New Pivot Logic)
    inv_map = {}
    stock_map = {}
    if f_inv:
        try:
            df_inv = pd.read_csv(f_inv, sep=';', engine='python', encoding='utf-8')
        except:
            f_inv.seek(0)
            df_inv = pd.read_csv(f_inv, sep=';', engine='python', encoding='ISO-8859-1')
        
        if 'zalando_article_variant' in df_inv.columns:
            # Aggregate Inventory per Zalando SKU (Sums stock across all sizes)
            df_inv['zfs_clean'] = df_inv['sellable_zfs_stock'].apply(clean_val)
            df_inv['pf_clean'] = df_inv['sellable_pf_stock'].apply(clean_val)
            
            # Pivot the inventory to match Config SKU
            inv_pivoted = df_inv.groupby('zalando_article_variant').agg({
                'article_name': 'first',
                'zfs_clean': 'sum',
                'pf_clean': 'sum'
            }).reset_index()
            
            inv_map = inv_pivoted.set_index('zalando_article_variant')['article_name'].to_dict()
            stock_map = inv_pivoted.set_index('zalando_article_variant')[['zfs_clean', 'pf_clean']].sum(axis=1).to_dict()
            
            df['ArticleName'] = df['Config SKU'].map(inv_map).fillna(df['Config SKU'])
            df['TotalStock'] = df['Config SKU'].map(stock_map).fillna(0)
    else:
        df['ArticleName'] = df['Config SKU']
        df['TotalStock'] = 9999 # Avoid false threats if no file is uploaded

    # --- TOP FILTERS (Added Automatic Latest Defaults) ---
    st.title(f"📊 {client_name} Strategic Board")
    
    years = sorted(df['Year'].unique(), reverse=True)
    c1, c2, c3 = st.columns(3)
    # Default to latest year
    sel_year = c1.selectbox("Filter Year", years, index=0)
    
    available_weeks = sorted(df[df['Year'] == sel_year]['Week'].unique(), reverse=True)
    # Default to latest week
    cw_w = c2.selectbox("Current Week", available_weeks, index=0)
    lw_w = c3.selectbox("Comparison Week", available_weeks, index=min(1, len(available_weeks)-1))

    # Sidebar: Gender and Market Filters (Preserved)
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
    def get_weekly_stats(week_num):
        subset = df_f[df_f['Week'] == week_num]
        stats = subset[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold', 'Impressions']].sum()
        stats['ROAS'] = stats['GMV'] / stats['Spend'] if stats['Spend'] > 0 else 0
        return stats

    s_cw = get_weekly_stats(cw_w)
    s_lw = get_weekly_stats(lw_w)

    # --- UI SECTION 1: KPI TILES (Preserved Logic) ---
    st.subheader(f"Performance Snapshot: Week {cw_w} vs Week {lw_w}")
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

    # --- UI SECTION 2: VISUAL ANALYTICS ---
    st.markdown("---")
    row2_1, row2_2 = st.columns([2, 1])

    with row2_1:
        st.subheader("Marketing Efficiency Trend")
        trend_data = df_f.groupby('Week').agg({'Spend':'sum', 'GMV':'sum'}).reset_index()
        trend_data['ROAS'] = trend_data['GMV'] / trend_data['Spend']
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=trend_data['Week'], y=trend_data['Spend']*multiplier, name="Spend", marker_color='#ff4b4b'), secondary_y=False)
        fig.add_trace(go.Bar(x=trend_data['Week'], y=trend_data['GMV']*multiplier, name="GMV", marker_color='#0068c9', opacity=0.6), secondary_y=False)
        fig.add_trace(go.Scatter(x=trend_data['Week'], y=trend_data['ROAS'], name="ROAS", line=dict(color='#2ecc71', width=3)), secondary_y=True)
        fig.update_layout(barmode='group', height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

    with row2_2:
        st.subheader("Top Wishlisted Styles")
        # Added Config SKU to Label
        wish_df = df_f[df_f['Week'] == cw_w].groupby(['ArticleName', 'Config SKU'])['Wish'].sum().reset_index()
        wish_df['ChartLabel'] = wish_df['ArticleName'] + " (" + wish_df['Config SKU'] + ")"
        wish_df = wish_df.sort_values('Wish', ascending=False).head(10)
        
        fig_wish = px.bar(wish_df, y='ChartLabel', x='Wish', orientation='h', color_discrete_sequence=['#ffaa00'])
        fig_wish.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), yaxis={'categoryorder':'total ascending'}, showlegend=False)
        st.plotly_chart(fig_wish, use_container_width=True)

    # --- UI SECTION 3: CAMPAIGN & STOCK THREAT ---
    st.markdown("---")
    st.subheader("📣 Campaign Level Breakdown & Stock Threats")
    
    # Calculate stock threats (Sold this week vs Total Pivoted Stock)
    camp_cw = df_f[df_f['Week'] == cw_w].groupby(['ZMS Campaign', 'Config SKU', 'ArticleName']).agg({
        'Spend':'sum', 'GMV':'sum', 'Wish':'sum', 'Sold':'sum', 'TotalStock':'max'
    }).reset_index()
    
    # Threat Logic: Items sold this week exceeds remaining inventory
    camp_cw['Stock Threat'] = camp_cw.apply(lambda x: "🚨 Sell Out Risk" if x['Sold'] >= x['TotalStock'] and x['TotalStock'] > 0 else ("✅ OK" if x['TotalStock'] > 0 else "❓ No Data"), axis=1)

    st.dataframe(
        camp_cw[['ZMS Campaign', 'ArticleName', 'Config SKU', 'Sold', 'TotalStock', 'Stock Threat', 'Spend', 'GMV', 'Wish']].sort_values('Sold', ascending=False),
        column_config={
            "Spend": st.column_config.NumberColumn(f"Spend {currency_label}", format=f"{currency_label}%.0f"),
            "GMV": st.column_config.NumberColumn(f"GMV {currency_label}", format=f"{currency_label}%.0f"),
            "Sold": "Sold (CW)",
            "TotalStock": "Stock Level"
        }, hide_index=True, use_container_width=True
    )

    # --- UI SECTION 4: STRATEGIC COMMENTARY (Dynamic Bulletpoints) ---
    st.markdown("---")
    st.subheader("📝 Strategic Observations")
    roas_trend = "positive" if s_cw['ROAS'] >= s_lw['ROAS'] else "negative"
    stock_threats = len(camp_cw[camp_cw['Stock Threat'] == "🚨 Sell Out Risk"])
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(f"""<div class="commentary-box"><strong>✅ What has improved</strong><ul><li>Efficiency trend is <b>{roas_trend}</b> for this period.</li><li>Customer desire for top wishlisted items remains strong.</li></ul></div>""", unsafe_allow_html=True)
    with col_b:
        st.markdown(f"""<div class="commentary-box"><strong>⚠️ Areas to optimize</strong><ul><li>Detected <b>{stock_threats}</b> articles with high sell-out risk in the coming week.</li><li>Review high-spend campaigns with ROAS below efficiency targets.</li></ul></div>""", unsafe_allow_html=True)
    with col_c:
        st.markdown("""<div class="commentary-box"><strong>🎯 Next Steps</strong><ul><li><b>Inventory:</b> Prioritize restock for "Sell Out Risk" articles.</li><li><b>Retargeting:</b> Push top wishlisted SKUs in high-ROAS markets.</li></ul></div>""", unsafe_allow_html=True)

else:
    st.title("📊 Strategic Marketplace Intelligence")
    st.info("👈 Please upload the **ZMS Market Report** and **Inventory Report** in the sidebar to populate the dashboard.")
