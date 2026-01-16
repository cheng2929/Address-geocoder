import streamlit as st
import pandas as pd
import googlemaps
from pyproj import Transformer
from PIL import Image
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import urllib3
import os
import json
import streamlit.components.v1 as components
from datetime import datetime, timedelta, timezone

# --- 設定 ---
urllib3.disable_warnings()

# --- 頁面設定 ---
try:
    icon_image = Image.open("icon.png")
    st.set_page_config(page_title="座標轉換通", page_icon=icon_image, layout="wide")
except:
    st.set_page_config(page_title="座標轉換通", page_icon="📍", layout="wide")

# --- CSS 樣式 (底部宣告) ---
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

# --- 初始化 Session State (用於暫存點位紀錄) ---
if 'saved_points' not in st.session_state:
    st.session_state['saved_points'] = []

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
    st.caption("若需「地址反查」請輸入 Key。")
    
    # 側邊欄顯示目前紀錄筆數
    if len(st.session_state['saved_points']) > 0:
        st.divider()
        st.metric("已紀錄點位", f"{len(st.session_state['saved_points'])} 筆")

# ==========================================
# 介面分頁 (已調整順序)
# ==========================================
# 順序：1.GPS -> 2.紀錄 -> 3.地圖 -> 4.單筆 -> 5.批次
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📍 GPS 定位", "📝 點位紀錄", "🔗 潛勢地圖", "🔍 單筆轉換", "📂 批次轉換"])

# ==========================================
# 分頁 1: 純 GPS 定位 + 儲存功能
# ==========================================
with tab1:
    # 教學區塊 (已修復亂碼問題)
    with st.expander("📲【教學】如何將此 APP 固定在手機桌面？"):
        c1, c2 = st.columns(2)
        with c1:
            ios_share_icon = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#007AFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path><polyline points="16 6 12 2 8 6"></polyline><line x1="12" y1="2" x2="12" y2="15"></line></svg>"""
            # 關鍵修正：加入 unsafe_allow_html=True
            st.markdown(f"### 🍎 iOS\nSafari 分享 ({ios_share_icon}) > 加入主畫面", unsafe_allow_html=True)
        with c2: 
            st.markdown("### 🤖 Android\nChrome 選單 > 加到主畫面")
    st.divider()
    
    # GPS 定位功能
    location = get_geolocation(component_key='get_geo')
    
    my_lat, my_lng, my_x, my_y, acc = None, None, None, None, None

    # 顯示座標數據
    if location and 'coords' in location:
        my_lat = location['coords']['latitude']
        my_lng = location['coords']['longitude']
        acc = location['coords']['accuracy']
        my_x, my_y = trans_to_twd97.transform(my_lng, my_lat)
        
        st.success(f"✅ 定位成功 (誤差 {acc:.0f}m)")
        c1, c2 = st.columns(2)
        with c1: st.metric("TWD97 X", f"{my_x:.3f}")
        with c2: st.metric("TWD97 Y", f"{my_y:.3f}")

        # 儲存點位按鈕
        col_save, col_note = st.columns([1, 3])
        with col_save:
            if st.button("💾 儲存目前點位", type="primary", use_container_width=True):
                # 取得台灣時間
                tz = timezone(timedelta(hours=8))
                now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
                
                # 加入紀錄列表
                new_record = {
                    "時間": now_str,
                    "經度 (Lon)": my_lng,
                    "緯度 (Lat)": my_lat,
                    "TWD97_X": my_x,
                    "TWD97_Y": my_y,
                    "誤差(m)": round(acc, 1)
                }
                st.session_state['saved_points'].append(new_record)
                st.toast(f"✅ 已儲存！目前共 {len(st.session_state['saved_points'])} 筆", icon="💾")
        
        with col_note:
            st.caption("💡 資料暫存於「📝 點位紀錄」分頁，離開前請記得匯出。")

    elif location and 'error' in location:
        st.error(f"定位失敗: {location['error']}")
    else:
        st.info("請點擊下方按鈕獲取定位")

    st.divider()

    # --- 定位地圖 ---
    st.markdown("### 🗺️ 定位地圖")
    map_center = [my_lat, my_lng] if my_lat else [22.75, 121.15]
    zoom_level = 16 if my_lat else 11
    
    m = folium.Map(location=map_center, zoom_start=zoom_level)

    if my_lat and my_lng:
        folium.Marker([my_lat, my_lng], popup="您的位置", icon=folium.Icon(color='red', icon='info-sign')).add_to(m)
    
    folium.LayerControl().add_to(m)
    st_folium(m, width="100%", height=400)

# ==========================================
# 分頁 2: 點位紀錄 (已移動至此)
# ==========================================
with tab2:
    st.subheader("📝 現場點位紀錄表")
    
    if len(st.session_state['saved_points']) > 0:
        # 轉成 DataFrame 顯示
        df_records = pd.DataFrame(st.session_state['saved_points'])
        
        # 顯示表格
        st.dataframe(df_records, use_container_width=True)
        
        col_dl, col_clear = st.columns([1, 1])
        
        with col_dl:
            # 匯出 CSV 按鈕
            csv = df_records.to_csv(index=False).encode('utf-8-sig')
            file_name = f"gps_records_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            st.download_button(
                label="📥 匯出紀錄 (CSV)",
                data=csv,
                file_name=file_name,
                mime="text/csv",
                type="primary",
                use_container_width=True
            )
            
        with col_clear:
            # 清除按鈕
            if st.button("🗑️ 清空所有紀錄", type="secondary", use_container_width=True):
                st.session_state['saved_points'] = []
                st.rerun()
    else:
        st.info("目前沒有紀錄。請至「📍 GPS 定位」分頁點擊「儲存目前點位」。")
        st.caption("注意：重新整理網頁會清空未下載的紀錄，請記得定期匯出。")

# ==========================================
# 分頁 3: 潛勢地圖
# ==========================================
with tab3:
    st.markdown("### 🔗 土石流潛勢地圖")
    your_map_link = "https://www.google.com/maps/d/u/0/embed?mid=1eYJ5XO2j4dhyO1AGnrtbTAGhdL1Yyak&ehbc=2E312F"
    st.link_button("🚀 在 Google Maps App 開啟 (顯示定位點)", your_map_link, use_container_width=True)
    st.caption("點擊上方按鈕可開啟手機 App 導航。下方為預覽視窗：")
    try:
        components.iframe(your_map_link, height=600)
    except Exception as e:
        st.error("地圖載入失敗。")

# ==========================================
# 分頁 4: 單筆轉換
# ==========================================
with tab4:
    st.subheader("單筆手動轉換")
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
# 分頁 5: 批次轉換
# ==========================================
with tab5:
    st.subheader("批次地址轉換")
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
