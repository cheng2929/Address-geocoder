import streamlit as st
import pandas as pd
import googlemaps
from pyproj import Transformer
from PIL import Image
import time
import requests
import json

# --- 設定與常數 ---
# Google 精度類型翻譯
GOOGLE_TYPE_MAPPING = {
    "ROOFTOP": "🎯 精準定位 (屋頂/門牌)",
    "RANGE_INTERPOLATED": "📏 推估位置 (門牌區間)",
    "GEOMETRIC_CENTER": "📍 幾何中心 (道路/區域)",
    "APPROXIMATE": "⭕ 粗略位置 (大範圍)"
}

# TGOS 精度類型翻譯
TGOS_TYPE_MAPPING = {
    "完全比對": "🎯 精準定位 (完全比對)",
    "門牌比對": "🎯 精準定位 (門牌號碼)",
    "路街比對": "📍 模糊比對 (僅到路街)",
    "路街巷弄比對": "📍 模糊比對 (僅到巷弄)",
    "鄉鎮市區比對": "⭕ 粗略位置 (僅到鄉鎮市區)"
}

# --- 頁面設定 ---
try:
    icon_image = Image.open("icon.png")
    st.set_page_config(page_title="地址座標轉換神器", page_icon=icon_image, layout="wide")
except FileNotFoundError:
    st.set_page_config(page_title="地址座標轉換神器", page_icon="🗺️", layout="wide")

st.title("🗺️ 地址與座標轉換工具 (Google/TGOS 雙引擎終極版)")

# --- ⚠️ 重要聲明 ---
st.warning("⚠️ **聲明：此APP為阿誠開發維護，API使用可能產生費用或受IP限制，請依規範使用。**")

# --- 初始化座標轉換器 ---
@st.cache_resource
def get_transformers():
    to_twd97 = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
    to_wgs84 = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)
    return to_twd97, to_wgs84

trans_to_twd97, trans_to_wgs84 = get_transformers()

# --- 側邊欄：設定 API Keys ---
st.sidebar.header("⚙️ 引擎設定")
with st.sidebar.expander("Google Maps 設定", expanded=True):
    google_api_key = st.text_input("Google API Key", type="password", help="用於 Google 引擎轉換。")

with st.sidebar.expander("TGOS (內政部) 設定", expanded=True):
    st.caption("需至 TGOS 平台申請，且受 IP 與頻率限制。")
    tgos_appid = st.text_input("TGOS APPID", help="請輸入您的 TGOS APPID")
    tgos_apikey = st.text_input("TGOS APIKey", type="password", help="請輸入您的 TGOS APIKey")

# ==========================================
# 核心功能函式庫 (保持不變)
# ==========================================
def use_google_engine(addr, api_key):
    """使用 Google API 查詢"""
    if not api_key: return None, "未設定 Google API Key"
    gmaps = googlemaps.Client(key=api_key)
    try:
        geocode_result = gmaps.geocode(addr)
        if geocode_result:
            result = geocode_result[0]
            lat = result['geometry']['location']['lat']
            lng = result['geometry']['location']['lng']
            loc_type_raw = result['geometry']['location_type']
            loc_type_zh = GOOGLE_TYPE_MAPPING.get(loc_type_raw, loc_type_raw)
            x, y = trans_to_twd97.transform(lng, lat)
            return {"source": "Google", "lat": lat, "lng": lng, "twd97_x": x, "twd97_y": y, "accuracy_zh": loc_type_zh}, None
        return None, "Google 查無此地址"
    except Exception as e: return None, f"Google API 錯誤: {e}"

def use_tgos_engine(addr, appid, apikey):
    """使用 TGOS API 查詢"""
    if not appid or not apikey: return None, "未設定 TGOS APPID 或 APIKey"
    tgos_url = "https://gis.tgos.tw/TGOS_MAP_API/Web/Address/TGOS_Address.aspx"
    params = {'oAPPId': appid, 'oAPIKey': apikey, 'Address': addr, 'SRS': 'EPSG:3826', 'FuzzyType': '2', 'ResultDataType': 'JSON', 'FuzzyNumber': '1', 'IsOnlyFullMatch': 'false', 'Columnname': 'Geometry'}
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(tgos_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            clean_text = response.text.strip()
            if clean_text.startswith(u'\ufeff'): clean_text = clean_text[1:]
            data = json.loads(clean_text)
            if 'AddressList' in data and len(data['AddressList']) > 0:
                top_result = data['AddressList'][0]
                twd97_x = float(top_result['X'])
                twd97_y = float(top_result['Y'])
                match_type_raw = top_result.get('MatchType', '未知')
                match_type_zh = TGOS_TYPE_MAPPING.get(match_type_raw, f"TGOS: {match_type_raw}")
                lng, lat = trans_to_wgs84.transform(twd97_x, twd97_y)
                return {"source": "TGOS", "lat": lat, "lng": lng, "twd97_x": twd97_x, "twd97_y": twd97_y, "accuracy_zh": match_type_zh}, None
            elif 'Info' in data: return None, f"TGOS 回應: {data['Info'][0]}"
            else: return None, "TGOS 查無結果"
        else: return None, f"TGOS HTTP 錯誤: {response.status_code}"
    except Exception as e: return None, f"TGOS 連線/解析錯誤: {e}"

# ==========================================
# 介面分頁
# ==========================================
tab1, tab2 = st.tabs(["🔍 單筆轉換", "📂 批次轉換 (雙引擎)"])

# ==========================================
# 分頁 1: 單筆手動轉換 (功能保持不變)
# ==========================================
with tab1:
    st.subheader("單筆手動轉換")
    mode = st.radio("選擇功能：", ("🏠 地址 ➔ 座標", "🌐 經緯度 ➔ TWD97", "📐 TWD97 ➔ 經緯度"), horizontal=True)
    st.divider()

    if mode == "🏠 地址 ➔ 座標":
        engine = st.selectbox("選擇單筆搜尋引擎：", ["Google Maps", "TGOS (內政部)"], key="single_engine")
        if engine == "TGOS (內政部)": st.info("💡 TGOS 為官方圖資，請確認側邊欄已設定 TGOS 金鑰。")
        else: st.info("💡 Google Maps 全球通用，請確認側邊欄已設定 Google API Key。")

        input_addr = st.text_input("輸入地址", placeholder="例如：台北市信義區信義路五段7號")
        
        if st.button("查詢座標", type="primary"):
            if not input_addr: st.warning("請輸入地址。")
            else:
                with st.spinner(f"正在使用 {engine} 查詢中..."):
                    if engine == "Google Maps": result, error_msg = use_google_engine(input_addr, google_api_key)
                    else: result, error_msg = use_tgos_engine(input_addr, tgos_appid, tgos_apikey)
                
                if result:
                    st.success(f"✅ **[{result['source']}] 定位成功！** 精度: {result['accuracy_zh']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### 🌐 WGS84 (經緯度)")
                        st.code(f"{result['lat']:.6f}, {result['lng']:.6f}")
                        st.markdown(f"[👉 在 Google Maps 開啟確認](http://googleusercontent.com/maps.google.com/?q={result['lat']},{result['lng']})")
                    with col2:
                        st.markdown("#### 📐 TWD97 (二度分帶)")
                        st.code(f"X: {result['twd97_x']:.3f}\nY: {result['twd97_y']:.3f}")
                else: st.error(f"查詢失敗: {error_msg}")

    elif mode == "🌐 經緯度 ➔ TWD97":
        col1, col2 = st.columns(2)
        in_lat = col1.number_input("緯度 (Lat)", value=25.0339, format="%.6f")
        in_lng = col2.number_input("經度 (Lon)", value=121.5644, format="%.6f")
        if st.button("轉換為 TWD97"):
            x, y = trans_to_twd97.transform(in_lng, in_lat)
            st.success(f"轉換結果 (TWD97): X: {x:.3f}, Y: {y:.3f}")

    elif mode == "📐 TWD97 ➔ 經緯度":
        col1, col2 = st.columns(2)
        in_x = col1.number_input("X 座標 (E)", value=306812.0, format="%.3f")
        in_y = col2.number_input("Y 座標 (N)", value=2769213.0, format="%.3f")
        if st.button("轉換為經緯度"):
            lng, lat = trans_to_wgs84.transform(in_x, in_y)
            st.success(f"轉換結果 (WGS84): Lat: {lat:.6f}, Lon: {lng:.6f}")

# ==========================================
# 分頁 2: 批次轉換 (雙引擎升級版)
# ==========================================
with tab2:
    st.subheader("批次地址轉換 (支援雙引擎)")
    st.info("請上傳包含 `address` 欄位的 CSV 或 Excel 檔案。系統將自動新增座標、精度與來源欄位。")
    
    # 1. 上傳檔案
    uploaded_file = st.file_uploader("上傳檔案 (CSV/Excel)", type=['csv', 'xlsx'], key="batch_uploader")
    
    if uploaded_file:
        # 2. 選擇引擎
        batch_engine = st.selectbox("選擇批次搜尋引擎：", ["Google Maps", "TGOS (內政部)"], key="batch_engine_select")
        
        # 3. 檢查金鑰
        keys_ready = False
        if batch_engine == "Google Maps":
            if google_api_key: keys_ready = True
            else: st.error("❌ 請在側邊欄輸入 Google API Key 才能使用此引擎。")
        else: # TGOS
            if tgos_appid and tgos_apikey: keys_ready = True
            else: st.error("❌ 請在側邊欄輸入 TGOS APPID 和 APIKey 才能使用此引擎。")
            st.warning("⚠️ 注意：使用 TGOS 進行批次轉換時，請確保您的 IP 未被封鎖，且速度較慢以符合規範。")

        # 4. 開始轉換按鈕
        if keys_ready:
            if st.button(f"開始批次轉換 ({batch_engine})", type="primary"):
                try:
                    if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
                    else: df = pd.read_excel(uploaded_file)
                    
                    if 'address' not in df.columns:
                        st.error("錯誤：檔案中找不到 `address` 欄位。")
                    else:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        results_data = []
                        
                        # 開始迴圈
                        total_rows = len(df)
                        for i, addr in enumerate(df['address']):
                            # 根據選擇呼叫引擎
                            if batch_engine == "Google Maps":
                                result, error = use_google_engine(addr, google_api_key)
                            else:
                                result, error = use_tgos_engine(addr, tgos_appid, tgos_apikey)
                                # TGOS 需要休息一下避免被鎖
                                time.sleep(0.2) 

                            if result:
                                results_data.append([result['source'], result['lat'], result['lng'], result['twd97_x'], result['twd97_y'], result['accuracy_zh'], None])
                            else:
                                results_data.append([batch_engine, None, None, None, None, "查詢失敗", error])

                            # 更新進度
                            progress_bar.progress((i + 1) / total_rows)
                            status_text.text(f"正在使用 {batch_engine} 處理: {i+1}/{total_rows}")
                        
                        # 將結果寫入 DataFrame
                        df[['來源引擎', 'lat', 'lon', 'twd97_x', 'twd97_y', '精度說明', '錯誤訊息']] = results_data
                        
                        st.success("✅ 批次轉換完成！")
                        st.dataframe(df.head())
                        
                        # 下載按鈕
                        csv = df.to_csv(index=False).encode('utf-8-sig')
                        output_filename = f"result_{batch_engine.split(' ')[0].lower()}.csv"
                        st.download_button(f"下載結果 (CSV)", csv, output_filename, "text/csv")

                except Exception as e:
                    st.error(f"讀取檔案或處理時發生錯誤: {e}")
