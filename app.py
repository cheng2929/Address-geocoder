import streamlit as st
import pandas as pd
import googlemaps
from pyproj import Transformer
import time

# --- 頁面設定 ---
st.set_page_config(page_title="地址座標轉換神器", page_icon="🗺️", layout="wide")

st.title("🗺️ 地址與座標轉換工具")

# --- ⚠️ 重要聲明 ---
st.warning("⚠️ **聲明：此APP為阿誠開發維護，因API超過額度須收費，未經允許請勿他用。**")

# --- 初始化座標轉換器 (快取以提升效能) ---
@st.cache_resource
def get_transformers():
    # WGS84 (經緯度) 轉 TWD97
    to_twd97 = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
    # TWD97 轉 WGS84 (經緯度)
    to_wgs84 = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)
    return to_twd97, to_wgs84

trans_to_twd97, trans_to_wgs84 = get_transformers()

# --- 側邊欄：設定 API Key ---
st.sidebar.header("⚙️ 設定")
api_key = st.sidebar.text_input("輸入 Google Maps API Key", type="password", help="地址轉換功能需要此 Key，純座標轉換則不需要。")

# --- 核心功能函式 ---
def address_to_coords(gmaps, addr):
    """地址 -> 經緯度 + TWD97"""
    try:
        geocode_result = gmaps.geocode(addr)
        if geocode_result:
            lat = geocode_result[0]['geometry']['location']['lat']
            lng = geocode_result[0]['geometry']['location']['lng']
            # 轉 TWD97
            x, y = trans_to_twd97.transform(lng, lat)
            return lat, lng, x, y
        return None, None, None, None
    except Exception as e:
        return None, None, None, None

# --- 介面分頁 (已互換順序) ---
tab1, tab2 = st.tabs(["🔍 單筆轉換 (手動輸入)", "📂 批次轉換 (檔案上傳)"])

# ==========================================
# 分頁 1: 單筆手動轉換 (原本在後面，現在移到前面)
# ==========================================
with tab1:
    st.subheader("單筆手動轉換")
    
    # 選擇轉換模式
    mode = st.radio(
        "選擇轉換類型：",
        ("🏠 地址 ➔ 座標", "🌐 經緯度 (WGS84) ➔ TWD97", "📐 TWD97 ➔ 經緯度 (WGS84)"),
        horizontal=True
    )
    
    st.divider()

    # --- 模式 A: 地址轉座標 ---
    if mode == "🏠 地址 ➔ 座標":
        input_addr = st.text_input("輸入地址", placeholder="例如：台北市信義區信義路五段7號")
        
        if st.button("查詢座標"):
            if not api_key:
                st.error("此功能需要 Google Maps API Key，請在左側輸入。")
            elif not input_addr:
                st.warning("請輸入地址。")
            else:
                gmaps = googlemaps.Client(key=api_key)
                lat, lng, x, y = address_to_coords(gmaps, input_addr)
                
                if lat:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.success("✅ WGS84 (經緯度)")
                        st.code(f"{lat}, {lng}")
                        st.markdown(f"[在 Google Maps 查看](http://googleusercontent.com/maps.google.com/?q={lat},{lng})")
                    with col2:
                        st.info("✅ TWD97 (二度分帶)")
                        st.code(f"X: {x:.3f}\nY: {y:.3f}")
                else:
                    st.error("找不到該地址，請檢查輸入是否正確。")

    # --- 模式 B: 經緯度轉 TWD97 ---
    elif mode == "🌐 經緯度 (WGS84) ➔ TWD97":
        col1, col2 = st.columns(2)
        in_lat = col1.number_input("緯度 (Lat)", value=25.0339, format="%.6f")
        in_lng = col2.number_input("經度 (Lon)", value=121.5644, format="%.6f")
        
        if st.button("轉換為 TWD97"):
            x, y = trans_to_twd97.transform(in_lng, in_lat)
            st.success(f"轉換結果 (TWD97):")
            st.code(f"X: {x:.3f}\nY: {y:.3f}")

    # --- 模式 C: TWD97 轉 經緯度 ---
    elif mode == "📐 TWD97 ➔ 經緯度 (WGS84)":
        col1, col2 = st.columns(2)
        in_x = col1.number_input("X 座標 (E)", value=306812.0, format="%.3f")
        in_y = col2.number_input("Y 座標 (N)", value=2769213.0, format="%.3f")
        
        if st.button("轉換為經緯度"):
            lng, lat = trans_to_wgs84.transform(in_x, in_y)
            st.success(f"轉換結果 (WGS84):")
            st.code(f"緯度 (Lat): {lat:.6f}\n經度 (Lon): {lng:.6f}")
            st.markdown(f"[在 Google Maps 查看](http://googleusercontent.com/maps.google.com/?q={lat},{lng})")

# ==========================================
# 分頁 2: 批次轉換 (原本在前面，現在移到後面)
# ==========================================
with tab2:
    st.subheader("批次地址轉換")
    st.info("請上傳包含 `address` 欄位的 CSV 或 Excel 檔案。")
    
    uploaded_file = st.file_uploader("上傳檔案", type=['csv', 'xlsx'])

    if uploaded_file:
        if not api_key:
            st.error("⚠️ 批次地址轉換需要 Google Maps API Key，請在左側輸入。")
        else:
            try:
                # 讀取檔案
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.write("預覽資料：", df.head())

                if 'address' not in df.columns:
                    st.error("錯誤：找不到 `address` 欄位。")
                else:
                    if st.button("開始批次轉換", type="primary"):
                        gmaps = googlemaps.Client(key=api_key)
                        
                        # 進度條
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        total = len(df)
                        
                        lats, lngs, xs, ys = [], [], [], []
                        
                        # 錯誤計數器
                        error_count = 0
                        
                        for i, addr in enumerate(df['address']):
                            lat, lng, x, y = address_to_coords(gmaps, addr)
                            lats.append(lat)
                            lngs.append(lng)
                            xs.append(x)
                            ys.append(y)
                            
                            if lat is None:
                                error_count += 1
                            
                            progress_bar.progress((i + 1) / total)
                            status_text.text(f"處理中: {i+1}/{total}")
                            
                        df['lat'] = lats
                        df['lon'] = lngs
                        df['twd97_x'] = xs
                        df['twd97_y'] = ys
                        
                        st.success("轉換完成！")
                        if error_count > 0:
                            st.warning(f"注意：有 {error_count} 筆地址無法辨識或查無結果。")
                            
                        st.dataframe(df)
                        
                        # 下載
                        csv = df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button("下載結果 (CSV)", csv, "result.csv", "text/csv")

            except Exception as e:
                st.error(f"發生錯誤: {e}")
