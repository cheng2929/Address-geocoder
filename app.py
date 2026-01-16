import streamlit as st
import pandas as pd
import googlemaps
from pyproj import Transformer
from PIL import Image
import re # 用於處理字串

# --- 設定：關閉不必要的警告 ---
import urllib3
urllib3.disable_warnings()

# --- 設定與常數 ---
GOOGLE_TYPE_MAPPING = {
    "ROOFTOP": "🎯 精準定位 (屋頂/門牌)",
    "RANGE_INTERPOLATED": "📏 推估位置 (門牌區間)",
    "GEOMETRIC_CENTER": "📍 幾何中心 (道路/區域)",
    "APPROXIMATE": "⭕ 粗略位置 (大範圍)"
}

# --- 頁面設定 ---
try:
    icon_image = Image.open("icon.png")
    st.set_page_config(page_title="地址座標轉換神器", page_icon=icon_image, layout="wide")
except FileNotFoundError:
    st.set_page_config(page_title="地址座標轉換神器", page_icon="🗺️", layout="wide")

st.title("🗺️ 地址與座標轉換工具 (Google API + GPS 工具)")

# --- ⚠️ 重要聲明 ---
st.warning("⚠️ **聲明：此APP為阿誠開發維護，Google API 使用可能產生費用，請依規範使用。**")

# --- 初始化座標轉換器 ---
@st.cache_resource
def get_transformers():
    # WGS84 (經緯度) <-> TWD97
    to_twd97 = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
    to_wgs84 = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)
    return to_twd97, to_wgs84

trans_to_twd97, trans_to_wgs84 = get_transformers()

# --- 側邊欄：設定 API Keys ---
st.sidebar.header("⚙️ 設定")
google_api_key = st.sidebar.text_input("Google API Key", type="password", help="地址轉換功能需要此 Key。")

# ==========================================
# 核心功能函式庫
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

def dms_to_dd(d, m, s):
    """度分秒 -> 十進位經緯度"""
    try:
        dd = float(d) + float(m)/60 + float(s)/3600
        return dd
    except:
        return 0.0

# ==========================================
# 介面分頁
# ==========================================
tab1, tab2, tab3 = st.tabs(["🔍 單筆轉換 (地址)", "📂 批次轉換 (檔案)", "🛰️ GPS 格式轉換 (度分秒)"])

# ==========================================
# 分頁 1: 單筆手動轉換 (地址/座標互轉)
# ==========================================
with tab1:
    st.subheader("單筆手動轉換")
    mode = st.radio("選擇功能：", ("🏠 地址 ➔ 座標", "🌐 經緯度 (Decimal) ➔ TWD97", "📐 TWD97 ➔ 經緯度"), horizontal=True)
    st.divider()

    if mode == "🏠 地址 ➔ 座標":
        st.info("💡 使用 Google Maps 引擎。")
        input_addr = st.text_input("輸入地址", placeholder="例如：台東市中華路一段684號")
        if st.button("查詢座標", type="primary"):
            if not input_addr: st.warning("請輸入地址。")
            else:
                with st.spinner("查詢中..."):
                    result, error_msg = use_google_engine(input_addr, google_api_key)
                if result:
                    st.success(f"✅ 定位成功！精度: {result['accuracy_zh']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### 🌐 WGS84 (經緯度)")
                        st.code(f"{result['lat']:.6f}, {result['lng']:.6f}")
                        st.markdown(f"[👉 Google Maps 確認](http://googleusercontent.com/maps.google.com/?q={result['lat']},{result['lng']})")
                    with col2:
                        st.markdown("#### 📐 TWD97 (二度分帶)")
                        st.code(f"X: {result['twd97_x']:.3f}\nY: {result['twd97_y']:.3f}")
                else: st.error(f"查詢失敗: {error_msg}")

    elif mode == "🌐 經緯度 (Decimal) ➔ TWD97":
        c1, c2 = st.columns(2)
        in_lat = c1.number_input("緯度 (Lat)", value=22.7550, format="%.6f")
        in_lng = c2.number_input("經度 (Lon)", value=121.1500, format="%.6f")
        if st.button("轉換 TWD97"):
            x, y = trans_to_twd97.transform(in_lng, in_lat)
            st.success(f"轉換結果 (TWD97): X: {x:.3f}, Y: {y:.3f}")

    elif mode == "📐 TWD97 ➔ 經緯度":
        c1, c2 = st.columns(2)
        in_x = c1.number_input("X 座標 (E)", value=260000.0, format="%.3f")
        in_y = c2.number_input("Y 座標 (N)", value=2500000.0, format="%.3f")
        if st.button("轉換經緯度"):
            lng, lat = trans_to_wgs84.transform(in_x, in_y)
            st.success(f"轉換結果 (WGS84): Lat: {lat:.6f}, Lon: {lng:.6f}")

# ==========================================
# 分頁 2: 批次轉換 (Google)
# ==========================================
with tab2:
    st.subheader("批次地址轉換")
    st.info("請上傳包含 `address` 欄位的 CSV/Excel。使用 Google API。")
    uploaded_file = st.file_uploader("上傳檔案", type=['csv', 'xlsx'])

    if uploaded_file:
        if not google_api_key:
            st.error("請先在側邊欄輸入 Google API Key。")
        else:
            if st.button("開始批次轉換", type="primary"):
                try:
                    if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
                    else: df = pd.read_excel(uploaded_file)
                    
                    if 'address' not in df.columns:
                        st.error("找不到 `address` 欄位。")
                    else:
                        progress_bar = st.progress(0)
                        results = []
                        for i, addr in enumerate(df['address']):
                            res, err = use_google_engine(addr, google_api_key)
                            if res: results.append([res['lat'], res['lng'], res['twd97_x'], res['twd97_y'], res['accuracy_zh']])
                            else: results.append([None, None, None, None, err])
                            progress_bar.progress((i+1)/len(df))
                        
                        df[['lat', 'lon', 'twd97_x', 'twd97_y', '精度']] = results
                        st.success("完成！")
                        st.dataframe(df.head())
                        csv = df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button("下載 CSV", csv, "result.csv", "text/csv")
                except Exception as e: st.error(f"錯誤: {e}")

# ==========================================
# 分頁 3: GPS 格式轉換 (新功能)
# ==========================================
with tab3:
    st.subheader("🛰️ GPS 度分秒 (DMS) 轉換工具")
    st.markdown("將手持 GPS 常見的 **度(°)、分(')、秒(\")** 格式轉換為 **十進位經緯度** 與 **TWD97**。")
    
    col_gps_1, col_gps_2 = st.columns(2)
    
    # 輸入區塊：緯度
    with col_gps_1:
        st.markdown("#### 緯度 (Latitude / N)")
        lat_d = st.number_input("度 (Deg)", min_value=0, max_value=90, value=22, step=1)
        lat_m = st.number_input("分 (Min)", min_value=0, max_value=60, value=45, step=1)
        lat_s = st.number_input("秒 (Sec)", min_value=0.0, max_value=60.0, value=18.5, format="%.4f")
    
    # 輸入區塊：經度
    with col_gps_2:
        st.markdown("#### 經度 (Longitude / E)")
        lon_d = st.number_input("度 (Deg) ", min_value=0, max_value=180, value=121, step=1)
        lon_m = st.number_input("分 (Min) ", min_value=0, max_value=60, value=9, step=1)
        lon_s = st.number_input("秒 (Sec) ", min_value=0.0, max_value=60.0, value=0.0, format="%.4f")

    st.divider()

    if st.button("🔄 開始轉換 (GPS -> 座標)", type="primary"):
        # 計算十進位
        final_lat = dms_to_dd(lat_d, lat_m, lat_s)
        final_lon = dms_to_dd(lon_d, lon_m, lon_s)
        
        # 計算 TWD97
        t97_x, t97_y = trans_to_twd97.transform(final_lon, final_lat)
        
        st.success("轉換完成！")
        
        res_col1, res_col2 = st.columns(2)
        with res_col1:
            st.info("🌐 **WGS84 (十進位經緯度)**")
            st.code(f"{final_lat:.6f}, {final_lon:.6f}")
            st.markdown(f"[👉 在 Google Maps 查看](http://googleusercontent.com/maps.google.com/?q={final_lat},{final_lon})")
            
        with res_col2:
            st.warning("📐 **TWD97 (二度分帶座標)**")
            st.code(f"X: {t97_x:.3f}\nY: {t97_y:.3f}")
            
        st.markdown("---")
        st.caption(f"原始輸入: N {lat_d}°{lat_m}'{lat_s}\" , E {lon_d}°{lon_m}'{lon_s}\"")
