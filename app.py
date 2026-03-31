import streamlit as st
import pandas as pd
import re
import warnings
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

# --- CONFIGURATION ---
st.set_page_config(page_title="Strategic Marketing Intelligence", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e6e9ef; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stHeader"] { background-color: #000000; }
    .commentary-box { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #000000; margin-top: 10px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- UTILITY FUNCTIONS ---
def clean_val(val):
    if pd.isna(val) or val == '' or str(val).lower() == 'undefined': 
        return 0.0
    
    # 1. Gör till sträng och ta bort symboler
    s = str(val).strip().replace('€', '').replace('%', '').replace('SEK', '')
    
    # 2. Ta bort ALLA typer av mellanslag (inkl. tusentalsavgränsare som "28 846")
    s = re.sub(r'\s+', '', s)
    s = s.replace('\xa0', '') # Hanterar non-breaking spaces
    
    # 3. Hantera decimaler (komma -> punkt)
    if ',' in s:
        # Om det finns både punkt och komma (t.ex. 1.234,56), ta bort punkten först
        if '.' in s: s = s.replace('.', '')
        s = s.replace(',', '.')
    
    try: 
        return float(s)
    except: 
        return 0.0

def get_delta_pct(current, previous):
    if previous == 0: return 0.0
    return (current - previous) / previous

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/analytics.png", width=60)
    st.title("Settings")
    client_name = st.text_input("Brand", value="MQ Marqet")
    ex_rate = st.number_input("EUR to SEK", value=10.66)
    
    st.markdown("---")
    st.header("📅 Time Grain")
    view_type = st.radio("Analysis Level", ["Weekly", "Monthly"])
    
    st.markdown("---")
    st.header("📂 Data Source")
    f_mkt = st.file_uploader("1. ZMS Market Report (CSV)", type="csv")
    f_inv = st.file_uploader("2. Inventory SKU Report (CSV)", type="csv")
    
    st.markdown("---")
    show_sek = st.checkbox("Show SEK Values", value=False)
    currency_label = "kr" if show_sek else "€"
    multiplier = ex_rate if show_sek else 1.0

# --- MAIN LOGIC ---
if f_mkt:
    try:
        df = pd.read_csv(f_mkt, sep=';', engine='python', encoding='utf-8')
    except:
        f_mkt.seek(0)
        df = pd.read_csv(f_mkt, sep=';', engine='python', encoding='ISO-8859-1')
    
    df.columns = [c.strip() for c in df.columns]
    
    # Rengör alla numeriska kolumner
    m_cols = {
        'Spend': 'Budget spent', 'GMV': 'GMV', 'Wish': 'Add to wishlist', 
        'Clicks': 'Clicks', 'Sold': 'Items sold', 'Impressions': 'Viewable ad impressions'
    }
    for k, v in m_cols.items():
        if v in df.columns: 
            df[k] = df[v].apply(clean_val)
        else: 
            df[k] = 0.0

    # Hantera Inventory/Stock
    inv_map, stock_map = {}, {}
    if f_inv:
        try:
            df_inv = pd.read_csv(f_inv, sep=';', engine='python', encoding='utf-8')
        except:
            f_inv.seek(0)
            df_inv = pd.read_csv(f_inv, sep=';', engine='python', encoding='ISO-8859-1')
        
        df_inv.columns = [c.strip().lower() for c in df_inv.columns]
        sku_col = next((c for c in df_inv.columns if 'article_variant' in c), None)
        name_col = next((c for c in df_inv.columns if 'article_name' in c), None)
        
        if sku_col and name_col:
            df_inv[sku_col] = df_inv[sku_col].astype(str).str.strip().str.upper()
            df_inv['stock'] = df_inv.get('sellable_zfs_stock', 0).apply(clean_val) + df_inv.get('sellable_pf_stock', 0).apply(clean_val)
            inv_piv = df_inv.groupby(sku_col).agg({name_col: 'first', 'stock': 'sum'}).reset_index()
            inv_map = inv_piv.set_index(sku_col)[name_col].to_dict()
            stock_map = inv_piv.set_index(sku_col)['stock'].to_dict()

    df['Config SKU Match'] = df['Config SKU'].astype(str).str.strip().str.upper()
    df['ArticleName'] = df['Config SKU Match'].map(inv_map).fillna(df['Config SKU'])
    df['TotalStock'] = df['Config SKU Match'].map(stock_map).fillna(0)

    # --- FILTERS ---
    st.title(f"📊 {client_name} Strategic Board")
    time_col = 'Week' if view_type == "Weekly" else 'Month'
    
    c1, c2, c3 = st.columns(3)
    sel_year = c1.selectbox("Year", sorted(df['Year'].unique(), reverse=True))
    avail_p = sorted(df[df['Year'] == sel_year][time_col].unique(), reverse=True)
    curr_p = c2.selectbox(f"Current {time_col}", avail_p, index=0)
    last_p = c3.selectbox(f"Comparison {time_col}", avail_p, index=min(1, len(avail_p)-1))

    df_f = df[df['Year'] == sel_year].copy()
    
    # --- KPI TILES ---
    s_cw = df_f[df_f[time_col] == curr_p][['Spend', 'GMV', 'Wish', 'Clicks', 'Sold']].sum()
    s_lw = df_f[df_f[time_col] == last_p][['Spend', 'GMV', 'Wish', 'Clicks', 'Sold']].sum()
    
    roas_cw = s_cw['GMV']/s_cw['Spend'] if s_cw['Spend'] > 0 else 0
    roas_lw = s_lw['GMV']/s_lw['Spend'] if s_lw['Spend'] > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Spend", f"{currency_label}{s_cw['Spend']*multiplier:,.0f}", f"{get_delta_pct(s_cw['Spend'], s_lw['Spend']):.1%}", delta_color="inverse")
    k2.metric("GMV", f"{currency_label}{s_cw['GMV']*multiplier:,.0f}", f"{get_delta_pct(s_cw['GMV'], s_lw['GMV']):.1%}")
    k3.metric("ROAS", f"{roas_cw:.2f}x", f"{roas_cw - roas_lw:.2f} pts")
    k4.metric("Wishlists", f"{s_cw['Wish']:,.0f}", f"{get_delta_pct(s_cw['Wish'], s_lw['Wish']):.1%}")

    # --- MARKET ANALYSIS (NY SEKTION) ---
    st.markdown("---")
    st.subheader("🌍 Market Performance & Share")
    
    m_data = df_f[df_f[time_col] == curr_p].groupby('Market').agg({'Spend':'sum', 'GMV':'sum'}).reset_index()
    total_gmv = m_data['GMV'].sum()
    
    m_data['ROAS'] = m_data['GMV'] / m_data['Spend']
    m_data['COS %'] = (m_data['Spend'] / m_data['GMV'] * 100).fillna(0)
    m_data['GMV Share %'] = (m_data['GMV'] / total_gmv * 100).fillna(0)
    
    st.dataframe(
        m_data.sort_values('GMV', ascending=False),
        column_config={
            "Spend": st.column_config.NumberColumn(f"Spend {currency_label}", format=f"{currency_label}%.0f"),
            "GMV": st.column_config.NumberColumn(f"GMV {currency_label}", format=f"{currency_label}%.0f"),
            "ROAS": st.column_config.NumberColumn("ROAS", format="%.2fx"),
            "COS %": st.column_config.NumberColumn("COS", format="%.1f%%"),
            "GMV Share %": st.column_config.ProgressColumn("GMV Share", format="%.1f%%", min_value=0, max_value=100)
        }, hide_index=True, use_container_width=True
    )

    # --- VISUALS ---
    st.markdown("---")
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("Category Performance")
        cat_data = df_f[df_f[time_col] == curr_p].groupby('Category').agg({'Spend':'sum', 'GMV':'sum'}).reset_index()
        cat_data['ROAS'] = cat_data['GMV'] / cat_data['Spend']
        st.dataframe(cat_data.sort_values('GMV', ascending=False), use_container_width=True, hide_index=True)

    with col_right:
        st.subheader("Top Styles (Copy SKUs)")
        wish_df = df_f[df_f[time_col] == curr_p].groupby(['ArticleName', 'Config SKU'])['Wish'].sum().reset_index()
        wish_df = wish_df.sort_values('Wish', ascending=False).head(10)
        st.dataframe(wish_df[['Config SKU', 'ArticleName', 'Wish']], hide_index=True, use_container_width=True)

    # --- CAMPAIGN & STOCK ---
    st.markdown("---")
    st.subheader("📣 Campaign & Stock Status")
    camp_df = df_f[df_f[time_col] == curr_p].groupby(['ZMS Campaign', 'ArticleName', 'Config SKU']).agg({'Sold':'sum', 'TotalStock':'max', 'Spend':'sum', 'GMV':'sum'}).reset_index()
    camp_df['Stock Threat'] = camp_df.apply(lambda x: "🚨 Risk" if x['Sold'] >= x['TotalStock'] and x['TotalStock'] > 0 else "✅ OK", axis=1)
    st.dataframe(camp_df.sort_values('Sold', ascending=False), hide_index=True, use_container_width=True)

else:
    st.info("👈 Please upload the reports in the sidebar.")
