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

# Custom CSS for UI
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e6e9ef; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stHeader"] { background-color: #000000; }
    .commentary-box { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #000000; margin-top: 10px; margin-bottom: 20px; height: 100%; }
    .main { background-color: #f9fbff; }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITY FUNCTIONS ---
def clean_val(val):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': 
        return 0.0
    # Ta bort valutor, procent och mellanslag
    s = str(val).strip().replace('€', '').replace('%', '').replace('SEK', '')
    s = re.sub(r'[\s\xa0]+', '', s) 
    
    # Hantera decimaltecken (komma till punkt)
    if ',' in s:
        if '.' in s: 
            s = s.replace('.', '') # Ta bort tusentalsavgränsare om den är punkt
        s = s.replace(',', '.')
    
    try: 
        return float(s)
    except: 
        return 0.0

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
    st.header("📅 Time Grain")
    # Nyhet: Välj om du vill se veckor eller månader
    view_type = st.radio("Analysis Level", ["Weekly", "Monthly"])
    
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
    
    # Mapping & Cleaning
    m_cols = {
        'Spend': 'Budget spent', 'GMV': 'GMV', 'Wish': 'Add to wishlist', 
        'Clicks': 'Clicks', 'Sold': 'Items sold', 'Impressions': 'Viewable ad impressions'
    }
    for k, v in m_cols.items():
        if v in df.columns: 
            df[k] = df[v].apply(clean_val)
        else: 
            df[k] = 0.0

    # 2. LOAD INVENTORY DATA
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
    
    # Logik för Månads- eller Veckovalsmenyer
    time_col = 'Week' if view_type == "Weekly" else 'Month'
    time_label = "Week" if view_type == "Weekly" else "Month"
    
    available_periods = sorted(df[df['Year'] == sel_year][time_col].unique(), reverse=True)
    
    curr_p = c2.selectbox(f"Current {time_label}", available_periods, index=0)
    last_p = c3.selectbox(f"Comparison {time_label}", available_periods, index=min(1, len(available_periods)-1))

    # Sidebar: Target Filters
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
    def get_period_stats(period_val):
        subset = df_f[df_f[time_col] == period_val]
        stats = subset[['Spend', 'GMV', 'Wish', 'Clicks', 'Sold', 'Impressions']].sum()
        stats['ROAS'] = stats['GMV'] / stats['Spend'] if stats['Spend'] > 0 else 0
        return stats

    s_cw = get_period_stats(curr_p)
    s_lw = get_period_stats(last_p)

    # --- UI SECTION 1: KPI TILES ---
    st.subheader(f"Performance Snapshot: {time_label} {curr_p} vs {time_label} {last_p}")
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
        st.subheader(f"Marketing Efficiency Trend ({view_type})")
        trend_data = df_f.groupby(time_col).agg({'Spend':'sum', 'GMV':'sum'}).reset_index()
        trend_data['ROAS'] = trend_data['GMV'] / trend_data['Spend']
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=trend_data[time_col], y=trend_data['Spend']*multiplier, name="Spend", marker_color='#ff4b4b'), secondary_y=False)
        fig.add_trace(go.Bar(x=trend_data[time_col], y=trend_data['GMV']*multiplier, name="GMV", marker_color='#0068c9', opacity=0.6), secondary_y=False)
        fig.add_trace(go.Scatter(x=trend_data[time_col], y=trend_data['ROAS'], name="ROAS", line=dict(color='#2ecc71', width=3)), secondary_y=True)
        fig.update_layout(barmode='group', height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

    with row2_2:
        st.subheader("Top Wishlisted Styles")
        wish_df = df_f[df_f[time_col] == curr_p].groupby(['ArticleName', 'Config SKU'])['Wish'].sum().reset_index()
        wish_df = wish_df.sort_values('Wish', ascending=False).head(10)
        
        fig_wish = px.bar(
            wish_df, 
            y='ArticleName', 
            x='Wish', 
            orientation='h', 
            color_discrete_sequence=['#ffaa00'],
            hover_data=['Config SKU']
        )
        fig_wish.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_wish, use_container_width=True)
        
        # Nyhet: Tabell för att kunna kopiera Config SKU enkelt
        st.markdown("**Copy SKU List:**")
        st.dataframe(wish_df[['ArticleName', 'Config SKU', 'Wish']], hide_index=True, use_container_width=True)

    # --- NY SEKTION: CATEGORY PERFORMANCE ---
    st.markdown("---")
    st.subheader("📁 Performance by Category")
    
    cat_data = df_f[df_f[time_col] == curr_p].groupby('Category').agg({
        'Spend': 'sum',
        'GMV': 'sum'
    }).reset_index()
    
    cat_data['ROAS'] = cat_data['GMV'] / cat_data['Spend']
    cat_data['COS'] = cat_data['Spend'] / cat_data['GMV']
    
    # Hantera oändliga värden om spend/gmv är 0
    cat_data = cat_data.fillna(0).replace([float('inf'), float('-inf')], 0)
    
    st.dataframe(
        cat_data.sort_values('GMV', ascending=False),
        column_config={
            "Spend": st.column_config.NumberColumn(f"Spend {currency_label}", format=f"{currency_label}%.0f"),
            "GMV": st.column_config.NumberColumn(f"GMV {currency_label}", format=f"{currency_label}%.0f"),
            "ROAS": st.column_config.NumberColumn("ROAS", format="%.2fx"),
            "COS": st.column_config.NumberColumn("COS (%)", format="%.2f%%"),
        },
        hide_index=True,
        use_container_width=True
    )

    # --- UI SECTION 3: CAMPAIGN & STOCK THREAT ---
    st.markdown("---")
    st.subheader("📣 Campaign Level Breakdown & Stock Threats")
    
    camp_cw = df_f[df_f[time_col] == curr_p].groupby(['ZMS Campaign', 'Config SKU', 'ArticleName']).agg({
        'Spend':'sum', 'GMV':'sum', 'Wish':'sum', 'Sold':'sum', 'TotalStock':'max'
    }).reset_index()
    
    camp_cw['Stock Threat'] = camp_cw.apply(lambda x: "🚨 Sell Out Risk" if x['Sold'] >= x['TotalStock'] and x['TotalStock'] > 0 else ("✅ OK" if x['TotalStock'] > 0 else "❓ No Data"), axis=1)

    st.dataframe(
        camp_cw[['ZMS Campaign', 'ArticleName', 'Config SKU', 'Sold', 'TotalStock', 'Stock Threat', 'Spend', 'GMV', 'Wish']].sort_values('Sold', ascending=False),
        column_config={
            "Spend": st.column_config.NumberColumn(f"Spend {currency_label}", format=f"{currency_label}%.0f"),
            "GMV": st.column_config.NumberColumn(f"GMV {currency_label}", format=f"{currency_label}%.0f"),
            "Sold": f"Sold ({time_label})",
            "TotalStock": "Style Stock Level"
        }, hide_index=True, use_container_width=True
    )

    # --- UI SECTION 4: STRATEGIC COMMENTARY ---
    st.markdown("---")
    st.subheader("📝 Strategic Observations")
    roas_trend = "positive" if s_cw['ROAS'] >= s_lw['ROAS'] else "negative"
    stock_threats = len(camp_cw[camp_cw['Stock Threat'] == "🚨 Sell Out Risk"])
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(f"""<div class="commentary-box"><strong>✅ What has improved</strong><ul><li>Efficiency trend is <b>{roas_trend}</b> for this {time_label.lower()}.</li><li>Customer desire for top wishlisted items remains strong.</li></ul></div>""", unsafe_allow_html=True)
    with col_b:
        st.markdown(f"""<div class="commentary-box"><strong>⚠️ Areas to optimize</strong><ul><li>Detected <b>{stock_threats}</b> articles with high sell-out risk.</li><li>Review categories with high COS or ROAS below targets.</li></ul></div>""", unsafe_allow_html=True)
    with col_c:
        st.markdown("""<div class="commentary-box"><strong>🎯 Next Steps</strong><ul><li><b>Inventory:</b> Prioritize restock for "Sell Out Risk" articles.</li><li><b>Retargeting:</b> Push top wishlisted SKUs in high-ROAS categories.</li></ul></div>""", unsafe_allow_html=True)

else:
    st.title("📊 Strategic Marketplace Intelligence")
    st.info("👈 Please upload the **ZMS Market Report** and **Inventory Report** in the sidebar to populate the dashboard.")
