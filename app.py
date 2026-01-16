import streamlit as st
import pandas as pd
import googlemaps
from pyproj import Transformer
from PIL import Image
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import urllib3
import json
import os

# --- 設定 ---
urllib3.disable_warnings()

# --- 頁面設定 ---
try:
    icon_image = Image.open("icon.png")
    st.set_page_config(page_title="座標轉換通", page_icon=icon_image, layout="wide")
except:
    st.set_page_config(page_title="座標轉換通", page_icon="📍", layout="wide")

# --- CSS 樣式 ---
st.markdown("""
    <style>
        .footer {
            position: fixed; left: 0; bottom: 0; width: 100%;
            background-color: #f0f2f6; color: #555; text-align: center;
            padding: 10px; font-size: 14px; z-index: 999;
        }
        .main .block-container { padding-bottom: 80px; }
    </style>
""", unsafe_allow_html=True)

st.title("📍 現場座標轉換通")

# --- 初始化轉換器 ---
@st.cache_resource
def get_transformers():
    to_twd97 = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
    to_wgs84 = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)
    return to_twd97, to_wgs84

trans_to_twd97, trans_to_wgs84 = get_transformers()

# --- 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    google_api_key = st.text_input("Google API Key", type="password")
    st.caption("若需「地址反查」請輸入 Key，純 GPS 轉換免輸入。")

# ==========================================
# 介面分頁
# ==========================================
tab1, tab2, tab3 = st.tabs(["📍 GPS 與防災地圖", "🔍 地址/座標互轉", "📂 批次轉換"])

# ==========================================
# 分頁 1: 目前定位 + 土石流圖層
# ==========================================
with tab1:
    # 教學區塊 (摺疊)
    with st.expander("📲【教學】如何將此 APP 固定在手機桌面？"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🍎 iOS")
            st.markdown("Safari 分享 > 加入主畫面")
        with c2:
            st.markdown("### 🤖 Android")
            st.markdown("Chrome 選單 > 加到主畫面")

    st.divider()
    
    # 定位功能
    st.info("點擊按鈕獲取定位 (需允許權限)")
    location = get_geolocation(component_key='get_geo')
    
    # 預設地圖中心 (台東市) - 如果沒定位到就顯示這裡
    map_center = [22.75, 121.15]
    zoom_level = 11
    
    my_lat, my_lng = None, None

    if location and 'coords' in location:
        my_lat = location['coords']['latitude']
        my_lng = location['coords']['longitude']
        acc = location['coords']['accuracy']
        
        my_x, my_y = trans_to_twd97.transform(my_lng, my_lat)
        st.success(f"✅ 定位成功 (誤差 {acc:.0f}m)")
        
        c1, c2 = st.columns(2)
        with c1: st.metric("TWD97 X", f"{my_x:.3f}")
        with c2: st.metric("TWD97 Y", f"{my_y:.3f}")
        
        # 更新地圖中心為使用者位置
        map_center = [my_lat, my_lng]
        zoom_level = 16

    elif location and 'error' in location:
        st.error(f"定位失敗: {location['error']}")

    # --- 建立地圖 ---
    st.write("### 🗺️ 防災地圖 (含土石流潛勢)")
    m = folium.Map(location=map_center, zoom_start=zoom_level)

    # 1. 加上使用者位置圖釘
    if my_lat and my_lng:
        folium.Marker(
            [my_lat, my_lng], popup="您的位置", icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

    # 2. 載入「土石流潛勢溪流」圖層 (藍色線條)
    if os.path.exists("streams.geojson"):
        folium.GeoJson(
            "streams.geojson",
            name="🌊 土石流潛勢溪流",
            style_function=lambda x: {
                'color': 'blue', 'weight': 3, 'opacity': 0.7
            },
            tooltip=folium.GeoJsonTooltip(fields=['Debrisno'], aliases=['編號:']) # 依據欄位名稱調整
        ).add_to(m)
    
    # 3. 載入「土石流影響範圍」圖層 (黃色區塊)
    if os.path.exists("areas.geojson"):
        folium.GeoJson(
            "areas.geojson",
            name="⚠️ 土石流影響範圍",
            style_function=lambda x: {
                'fillColor': '#ffcc00', 'color': 'orange', 'weight': 1, 'fillOpacity': 0.4
            }
        ).add_to(m)

    # 4. 加入圖層控制器 (讓使用者可以開關圖層)
    folium.LayerControl().add_to(m)

    st_folium(m, width="100%", height=500)

# ==========================================
# 分頁 2: 單筆轉換
# ==========================================
with tab2:
    mode = st.radio("功能", ("🏠 地址➔座標", "🌐 經緯度➔97", "📐 97➔經緯度"), horizontal=True)
    if mode == "🏠 地址➔座標":
        addr = st.text_input("輸入地址")
        if st.button("查詢", use_container_width=True):
            if not google_api_key: st.error("需輸入 Google API Key")
            elif not addr: st.warning("請輸入地址")
            else:
                try:
                    gmaps = googlemaps.Client(key=google_api_key)
                    res = gmaps.geocode(addr)
                    if res:
                        lat = res[0]['geometry']['location']['lat']
                        lng = res[0]['geometry']['location']['lng']
                        x, y = trans_to_twd97.transform(lng, lat)
                        st.success("查詢成功")
                        st.code(f"X: {x:.3f}\nY: {y:.3f}")
                        st.markdown(f"[導航](http://googleusercontent.com/maps.google.com/?q={lat},{lng})")
                    else: st.error("查無結果")
                except Exception as e: st.error(str(e))

    elif mode == "🌐 經緯度➔97":
        lat = st.number_input("緯度", value=22.75)
        lng = st.number_input("經度", value=121.15)
        if st.button("轉換", use_container_width=True):
            x, y = trans_to_twd97.transform(lng, lat)
            st.code(f"X: {x:.3f}\nY: {y:.3f}")

    elif mode == "📐 97➔經緯度":
        x = st.number_input("X", value=260000.0)
        y = st.number_input("Y", value=2500000.0)
        if st.button("轉換", use_container_width=True):
            lng, lat = trans_to_wgs84.transform(x, y)
            st.code(f"{lat:.6f}, {lng:.6f}")

# ==========================================
# 分頁 3: 批次
# ==========================================
with tab3:
    st.info("上傳 Excel/CSV (需含 address 欄位)")
    uploaded_file = st.file_uploader("選擇檔案", type=['csv', 'xlsx'])
    if uploaded_file and google_api_key and st.button("開始轉換", type="primary", use_container_width=True):
        try:
            if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
            else: df = pd.read_excel(uploaded_file)
            gmaps = googlemaps.Client(key=google_api_key)
            results = []
            bar = st.progress(0)
            for i, row in df.iterrows():
                try:
                    res = gmaps.geocode(row['address'])
                    if res:
                        lat = res[0]['geometry']['location']['lat']
                        lng = res[0]['geometry']['location']['lng']
                        x, y = trans_to_twd97.transform(lng, lat)
                        results.append([lat, lng, x, y])
                    else: results.append([None]*4)
                except: results.append([None]*4)
                bar.progress((i+1)/len(df))
            df[['lat', 'lon', 'twd97_x', 'twd97_y']] = results
            st.dataframe(df.head())
            st.download_button("下載結果", df.to_csv(index=False).encode('utf-8-sig'), "result.csv", "text/csv", use_container_width=True)
        except Exception as e: st.error(str(e))

# --- 底部宣告 ---
st.markdown('<div class="footer">Made with ❤️ by 阿誠</div>', unsafe_allow_html=True)
