import streamlit as st
import pandas as pd
import googlemaps
from pyproj import Transformer
from PIL import Image
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import urllib3

# --- 設定 ---
urllib3.disable_warnings()

# --- 頁面設定 (手機優化) ---
try:
    icon_image = Image.open("icon.png")
    st.set_page_config(page_title="座標轉換通", page_icon=icon_image, layout="wide")
except:
    st.set_page_config(page_title="座標轉換通", page_icon="📍", layout="wide")

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
# 介面分頁 (GPS 優先)
# ==========================================
tab1, tab2, tab3 = st.tabs(["📍 GPS 定位", "🔍 地址/座標互轉", "📂 批次轉換"])

# ==========================================
# 分頁 1: 目前定位 (手機核心功能)
# ==========================================
with tab1:
    st.info("請點擊下方按鈕，並允許瀏覽器存取位置。")
    
    # 呼叫定位
    location = get_geolocation(component_key='get_geo')

    if location:
        my_lat = location['coords']['latitude']
        my_lng = location['coords']['longitude']
        accuracy = location['coords']['accuracy']
        
        # 轉 TWD97
        my_x, my_y = trans_to_twd97.transform(my_lng, my_lat)
        
        st.success(f"✅ 定位成功 (誤差: {accuracy:.0f}m)")
        
        # 手機版面：使用兩欄顯示數據
        c1, c2 = st.columns(2)
        with c1:
            st.metric("TWD97 X", f"{my_x:.3f}")
            st.metric("TWD97 Y", f"{my_y:.3f}")
        with c2:
            st.caption("WGS84 經緯度")
            st.text(f"{my_lat:.5f}, {my_lng:.5f}")

        # 顯示地圖
        m = folium.Map(location=[my_lat, my_lng], zoom_start=17)
        folium.Marker(
            [my_lat, my_lng], 
            popup="目前位置", 
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
        
        # 手機地圖高度設為 350px 比較剛好
        st_folium(m, width="100%", height=350)
    else:
        st.warning("等待定位中... (請確認手機 GPS 已開啟)")

# ==========================================
# 分頁 2: 單筆轉換 (工具箱)
# ==========================================
with tab2:
    mode = st.radio("功能", ("🏠 地址➔座標", "🌐 經緯度➔97", "📐 97➔經緯度"), horizontal=True)
    
    if mode == "🏠 地址➔座標":
        addr = st.text_input("輸入地址")
        if st.button("查詢", type="primary", use_container_width=True):
            if not google_api_key:
                st.error("需輸入 Google API Key")
            elif not addr:
                st.warning("請輸入地址")
            else:
                gmaps = googlemaps.Client(key=google_api_key)
                try:
                    res = gmaps.geocode(addr)
                    if res:
                        lat = res[0]['geometry']['location']['lat']
                        lng = res[0]['geometry']['location']['lng']
                        x, y = trans_to_twd97.transform(lng, lat)
                        st.success("查詢成功")
                        st.code(f"X: {x:.3f}\nY: {y:.3f}")
                        st.markdown(f"[開啟導航](https://www.google.com/maps/dir/?api=1&destination={lat},{lng})")
                    else:
                        st.error("查無結果")
                except Exception as e:
                    st.error(f"錯誤: {e}")

    elif mode == "🌐 經緯度➔97":
        lat = st.number_input("緯度 Lat", value=22.75)
        lng = st.number_input("經度 Lon", value=121.15)
        if st.button("轉換", use_container_width=True):
            x, y = trans_to_twd97.transform(lng, lat)
            st.code(f"X: {x:.3f}\nY: {y:.3f}")

    elif mode == "📐 97➔經緯度":
        x = st.number_input("X (E)", value=260000.0)
        y = st.number_input("Y (N)", value=2500000.0)
        if st.button("轉換", use_container_width=True):
            lng, lat = trans_to_wgs84.transform(x, y)
            st.code(f"{lat:.6f}, {lng:.6f}")
            st.markdown(f"[開啟導航](https://www.google.com/maps/dir/?api=1&destination={lat},{lng})")

# ==========================================
# 分頁 3: 批次 (維持簡單)
# ==========================================
with tab3:
    st.info("上傳 Excel/CSV (需含 address 欄位)")
    uploaded_file = st.file_uploader("選擇檔案", type=['csv', 'xlsx'])
    if uploaded_file and google_api_key:
        if st.button("開始轉換", type="primary", use_container_width=True):
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
                        else:
                            results.append([None, None, None, None])
                    except:
                        results.append([None, None, None, None])
                    bar.progress((i+1)/len(df))
                
                df[['lat', 'lon', 'twd97_x', 'twd97_y']] = results
                st.dataframe(df.head())
                st.download_button("下載結果", df.to_csv(index=False).encode('utf-8-sig'), "result.csv", "text/csv", use_container_width=True)
            except Exception as e:
                st.error(str(e))
