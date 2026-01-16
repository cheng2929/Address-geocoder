import streamlit as st
import pandas as pd
import googlemaps
from pyproj import Transformer
import time

# --- 頁面設定 ---
st.set_page_config(page_title="地址轉座標神器", page_icon="🗺️")

st.title("🗺️ 地址批次轉座標 (Google Maps + TWD97)")
st.markdown("""
這是一個協助將地址轉換為 **經緯度 (WGS84)** 與 **TWD97 (EPSG:3826)** 的工具。
請上傳包含 `address` 欄位的 CSV 或 Excel 檔案。
""")

# --- 側邊欄：設定 API Key ---
st.sidebar.header("設定")
api_key = st.sidebar.text_input("請輸入 Google Maps API Key", type="password")
st.sidebar.warning("注意：API Key 僅在當次運算使用，不會儲存。")

# --- 核心功能函式 ---
def get_location_data(gmaps, transformer, addr):
    if pd.isna(addr) or str(addr).strip() == "":
        return None, None, None, None
    try:
        geocode_result = gmaps.geocode(addr)
        if geocode_result:
            lat = geocode_result[0]['geometry']['location']['lat']
            lng = geocode_result[0]['geometry']['location']['lng']
            x, y = transformer.transform(lng, lat)
            return lat, lng, x, y
        else:
            return None, None, None, None
    except Exception as e:
        return None, None, None, None

# --- 主邏輯 ---
uploaded_file = st.file_uploader("上傳檔案 (CSV 或 Excel)", type=['csv', 'xlsx'])

if uploaded_file and api_key:
    # 讀取檔案
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.write("預覽上傳的資料：")
        st.dataframe(df.head())

        if 'address' not in df.columns:
            st.error("錯誤：檔案中找不到 `address` 欄位，請檢查表頭。")
        else:
            if st.button("開始轉換"):
                # 初始化工具
                gmaps = googlemaps.Client(key=api_key)
                transformer = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
                
                # 準備容器
                lats, lngs, xs, ys = [], [], [], []
                
                # 設定進度條
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_rows = len(df)
                
                # 執行迴圈
                for i, addr in enumerate(df['address']):
                    lat, lng, x, y = get_location_data(gmaps, transformer, addr)
                    lats.append(lat)
                    lngs.append(lng)
                    xs.append(x)
                    ys.append(y)
                    
                    # 更新進度
                    progress = (i + 1) / total_rows
                    progress_bar.progress(progress)
                    status_text.text(f"正在處理: {i+1}/{total_rows}")
                    
                    # 避免打太快 (視情況調整)
                    # time.sleep(0.05)
                
                # 寫回 DataFrame
                df['lat'] = lats
                df['lon'] = lngs
                df['twd97_x'] = xs
                df['twd97_y'] = ys
                
                st.success("轉換完成！")
                st.dataframe(df.head())
                
                # 下載按鈕
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="下載轉換結果 (CSV)",
                    data=csv,
                    file_name="converted_coordinates.csv",
                    mime="text/csv",
                )

    except Exception as e:
        st.error(f"讀取檔案發生錯誤: {e}")

elif uploaded_file and not api_key:
    st.info("請在左側側邊欄輸入 API Key 才能開始運算。")
