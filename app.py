import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import folium_static
import branca.colormap as cm

# 缓存机场数据加载
@st.cache_data
def load_airports_data():
    """加载机场CSV数据到内存"""
    try:
        df = pd.read_csv('airports.csv')
        df = df.dropna(subset=['iata_code']).reset_index(drop=True)
        return df
    except FileNotFoundError:
        st.error("错误：未找到 airports.csv 文件")
        return None

def haversine_distance(lat1, lon1, lat2, lon2):
    """使用Haversine公式计算两点之间的球面距离（单位：公里）"""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371
    return c * r

def find_nearby_airports(target_iata, radius_km, df):
    """查找目标机场周边指定半径内的所有机场"""
    target_airport = df[df['iata_code'] == target_iata.upper()]

    if target_airport.empty:
        return None, None

    target_lat = target_airport.iloc[0]['latitude_deg']
    target_lon = target_airport.iloc[0]['longitude_deg']

    df['distance_km'] = df.apply(
        lambda row: haversine_distance(target_lat, target_lon,
                                      row['latitude_deg'], row['longitude_deg']),
        axis=1
    )

    nearby = df[(df['distance_km'] <= radius_km) & (df['iata_code'] != target_iata.upper())]
    nearby = nearby.sort_values('distance_km').reset_index(drop=True)

    return target_airport.iloc[0], nearby

def create_professional_map(target_airport, nearby_airports, radius_km):
    """创建专业的交互式地图"""
    # 根据机场分布自动计算最佳缩放级别
    if len(nearby_airports) > 0:
        lats = [target_airport['latitude_deg']] + nearby_airports['latitude_deg'].tolist()
        lons = [target_airport['longitude_deg']] + nearby_airports['longitude_deg'].tolist()
        center_lat = np.mean(lats)
        center_lon = np.mean(lons)
        lat_range = max(lats) - min(lats)
        lon_range = max(lons) - min(lons)
        max_range = max(lat_range, lon_range)

        if max_range > 10:
            zoom_start = 4
        elif max_range > 5:
            zoom_start = 5
        elif max_range > 2:
            zoom_start = 6
        elif max_range > 1:
            zoom_start = 7
        else:
            zoom_start = 8
    else:
        center_lat = target_airport['latitude_deg']
        center_lon = target_airport['longitude_deg']
        zoom_start = 6

    # 创建地图，使用 CartoDB Voyager 底图（更美观）
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles='CartoDB Voyager',
        attr='© OpenStreetMap contributors, © CARTO'
    )

    # 添加备选底图选项
    folium.TileLayer(
        tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        attr='© OpenStreetMap contributors',
        name='OpenStreetMap'
    ).add_to(m)

    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        attr='© OpenStreetMap contributors, © CARTO',
        name='CartoDB Light'
    ).add_to(m)

    # 添加比例尺控件到右上角
    folium.plugins.MeasureControl(
        position='topright',
        primary_length_unit='kilometers',
        secondary_length_unit='miles',
        primary_area_unit='sqkilometers',
        secondary_area_unit='sqmiles'
    ).add_to(m)

    # 添加鼠标位置显示控件
    folium.plugins.MousePosition().add_to(m)

    # 添加全屏控件
    folium.plugins.Fullscreen(
        position='topright',
        title='全屏',
        title_cancel='退出全屏',
        force_separate_button=True
    ).add_to(m)

    # 创建图层组
    target_layer = folium.FeatureGroup(name='目标机场')
    nearby_layer = folium.FeatureGroup(name='附近机场')
    radius_layer = folium.FeatureGroup(name='搜索范围')
    connection_layer = folium.FeatureGroup(name='连接线')

    # 创建自定义图标HTML
    target_icon_html = '''
    <div style="
        background: linear-gradient(135deg, #ef5350 0%, #e53935 100%);
        width: 35px;
        height: 35px;
        border-radius: 50%;
        border: 3px solid white;
        box-shadow: 0 3px 10px rgba(239, 83, 80, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        ">
        <i class="fas fa-plane" style="color: white; font-size: 16px;"></i>
    </div>
    '''

    nearby_icon_html = '''
    <div style="
        background: linear-gradient(135deg, #42a5f5 0%, #1e88e5 100%);
        width: 30px;
        height: 30px;
        border-radius: 50%;
        border: 2px solid white;
        box-shadow: 0 3px 10px rgba(66, 165, 245, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        ">
        <i class="fas fa-plane" style="color: white; font-size: 14px;"></i>
    </div>
    '''

    # 添加目标机场标记（红色）
    target_popup = f"""
    <div style="font-family: Arial, sans-serif; min-width: 200px;">
        <h4 style="margin: 0 0 10px 0; color: #e53935; border-bottom: 2px solid #e53935; padding-bottom: 5px;">
            <i class="fas fa-plane"></i> {target_airport['name']}
        </h4>
        <p style="margin: 5px 0;"><strong>IATA码:</strong> {target_airport['iata_code']}</p>
        <p style="margin: 5px 0;"><strong>城市:</strong> {target_airport['municipality'] if pd.notna(target_airport['municipality']) else '未知'}</p>
        <p style="margin: 5px 0;"><strong>国家:</strong> {target_airport['iso_country']}</p>
        <p style="margin: 5px 0;"><strong>类型:</strong> {target_airport['type'].replace('_', ' ').title()}</p>
    </div>
    """

    target_marker = folium.Marker(
        location=[target_airport['latitude_deg'], target_airport['longitude_deg']],
        popup=folium.Popup(target_popup, max_width=300),
        tooltip=f"目标机场: {target_airport['name']}",
        icon=folium.DivIcon(
            html=target_icon_html,
            icon_size=(35, 35),
            icon_anchor=(17, 17),
            class_name='target-airport-marker'
        )
    )
    target_marker.add_to(target_layer)

    # 添加搜索半径圆圈
    radius_circle = folium.Circle(
        location=[target_airport['latitude_deg'], target_airport['longitude_deg']],
        radius=radius_km * 1000,
        color='#667eea',
        fill=True,
        fill_color='#667eea',
        fill_opacity=0.1,
        weight=2,
        dash_array='10, 10',
        popup=f'<b>搜索半径</b>: {radius_km} 公里'
    )
    radius_circle.add_to(radius_layer)

    # 添加附近机场标记（蓝色）并连线
    for _, airport in nearby_airports.iterrows():
        nearby_popup = f"""
        <div style="font-family: Arial, sans-serif; min-width: 200px;">
            <h4 style="margin: 0 0 10px 0; color: #1e88e5; border-bottom: 2px solid #1e88e5; padding-bottom: 5px;">
                <i class="fas fa-plane"></i> {airport['name']}
            </h4>
            <p style="margin: 5px 0;"><strong>IATA码:</strong> {airport['iata_code']}</p>
            <p style="margin: 5px 0;"><strong>城市:</strong> {airport['municipality'] if pd.notna(airport['municipality']) else '未知'}</p>
            <p style="margin: 5px 0;"><strong>国家:</strong> {airport['iso_country']}</p>
            <p style="margin: 5px 0;"><strong>距离:</strong> <span style="color: #667eea; font-weight: bold;">{airport['distance_km']:.1f}</span> 公里</p>
            <p style="margin: 5px 0;"><strong>类型:</strong> {airport['type'].replace('_', ' ').title()}</p>
        </div>
        """

        nearby_marker = folium.Marker(
            location=[airport['latitude_deg'], airport['longitude_deg']],
            popup=folium.Popup(nearby_popup, max_width=300),
            tooltip=f"{airport['name']} ({airport['distance_km']:.1f}km)",
            icon=folium.DivIcon(
                html=nearby_icon_html,
                icon_size=(30, 30),
                icon_anchor=(15, 15),
                class_name='nearby-airport-marker'
            )
        )
        nearby_marker.add_to(nearby_layer)

        connection_line = folium.PolyLine(
            locations=[
                [target_airport['latitude_deg'], target_airport['longitude_deg']],
                [airport['latitude_deg'], airport['longitude_deg']]
            ],
            color='gray',
            weight=1,
            opacity=0.4,
            dash_array='5, 10'
        )
        connection_line.add_to(connection_layer)

    # 将所有图层添加到地图
    radius_layer.add_to(m)
    connection_layer.add_to(m)
    nearby_layer.add_to(m)
    target_layer.add_to(m)

    # 添加图层控制
    folium.LayerControl(position='bottomright').add_to(m)

    # 添加图例
    legend_html = '''
    <div style="
        position: fixed;
        bottom: 50px;
        left: 50px;
        z-index: 1000;
        background: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        font-family: Arial, sans-serif;
    ">
        <h4 style="margin: 0 0 10px 0;">图例</h4>
        <p style="margin: 5px 0;">
            <i class="fas fa-plane" style="color: #e53935;"></i> 目标机场
        </p>
        <p style="margin: 5px 0;">
            <i class="fas fa-plane" style="color: #1e88e5;"></i> 附近机场
        </p>
        <p style="margin: 5px 0;">
            <div style="
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: rgba(102, 126, 234, 0.2);
                border: 2px dashed #667eea;
                display: inline-block;
                vertical-align: middle;
            "></div> 搜索范围
        </p>
        <p style="margin: 5px 0;">
            <div style="
                width: 20px;
                height: 2px;
                background: gray;
                display: inline-block;
                vertical-align: middle;
            "></div> 连接线
        </p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    return m

def main():
    """主应用函数"""
    st.set_page_config(
        page_title="全球机场搜索",
        page_icon="✈️",
        layout="wide"
    )

    st.title("✈️ 全球机场附近搜索")
    st.markdown("输入目标机场的IATA三字码，查找其周边指定范围内的其他机场")

    airports_df = load_airports_data()

    if airports_df is None:
        return

    col1, col2 = st.columns([1, 3])

    with col1:
        st.subheader("🔍 搜索参数")

        target_iata = st.text_input(
            "目标机场IATA码",
            value="PEK",
            max_chars=3,
            help="例如：PEK、LAX、CDG"
        ).upper()

        radius_km = st.slider(
            "搜索半径（公里）",
            min_value=50,
            max_value=1000,
            value=300,
            step=50
        )

        search_btn = st.button("🚀 查找附近机场", use_container_width=True)

        st.divider()

        st.info(f"📊 数据库包含 {len(airports_df):,} 个机场")

    if search_btn or target_iata:
        with st.spinner("正在搜索附近机场..."):
            target_airport, nearby_airports = find_nearby_airports(target_iata, radius_km, airports_df)

        if target_airport is None:
            st.error(f"❌ 未找到IATA码为 '{target_iata}' 的机场")
            return

        with col2:
            st.success(f"✅ 已找到 {len(nearby_airports)} 个附近机场")

            col_info1, col_info2, col_info3, col_info4 = st.columns(4)
            col_info1.metric("目标机场", target_airport['iata_code'])
            col_info2.metric("城市", target_airport['municipality'] if pd.notna(target_airport['municipality']) else '未知')
            col_info3.metric("国家", target_airport['iso_country'])
            col_info4.metric("搜索半径", f"{radius_km} km")

            st.subheader("📋 附近机场列表")

            if len(nearby_airports) > 0:
                display_df = nearby_airports[['name', 'iata_code', 'municipality', 'iso_country', 'distance_km']].head(20).copy()
                display_df.columns = ['机场名称', 'IATA码', '城市', '国家', '距离(km)']
                display_df['距离(km)'] = display_df['距离(km)'].round(1)
                st.dataframe(display_df, use_container_width=True, hide_index=True)

                if len(nearby_airports) > 20:
                    st.info(f"显示前 20 个结果，共 {len(nearby_airports)} 个")

            st.subheader("🗺️ 地图可视化")

            m = create_professional_map(target_airport, nearby_airports, radius_km)
            folium_static(m, width=1100, height=650)

if __name__ == "__main__":
    main()
