import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. 페이지 기본 설정 & 모던 커스텀 CSS
# ==========================================
st.set_page_config(
    page_title="전국 고령화 빅데이터 대시보드",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 모던/트렌디 스타일링 CSS 적용
st.markdown("""
<style>
    /* 메인 배경 및 기본 폰트 */
    .stApp {
        background-color: #f8fafc;
    }
    
    /* 헤더 타이틀 스타일 */
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1e293b 0%, #3b82f6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    /* 모던 KPI 카드 디자인 (Glassmorphism) */
    .kpi-card {
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08);
    }
    .kpi-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #0f172a;
    }
    .kpi-sub {
        font-size: 0.8rem;
        color: #3b82f6;
        font-weight: 500;
        margin-top: 4px;
    }

    /* 탭 스타일 개편 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #e2e8f0;
        padding: 6px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        border-radius: 8px;
        font-weight: 600;
        color: #475569;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #1e293b !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
</style>
""", unsafe_allow_html=True)

# 헤더 영역
st.markdown('<div class="main-header">⚡ 전국 고령화 시계열 빅데이터 대시보드</div>', unsafe_allow_html=True)
st.markdown("<p style='color: #64748b; font-size: 1.05rem; margin-bottom: 2rem;'>2015년~2026년 인구 데이터 기반 고령화 지형도 · 2035 미래 예측 · 시도별 트리맵 인사이더</p>", unsafe_allow_html=True)

# ==========================================
# 2. 데이터 불러오기 및 전처리
# ==========================================
@st.cache_data
def load_population_data():
    """인구 데이터를 불러오고 연도별·시군구별 고령화율을 계산합니다."""
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(pop_url, dtype={"코드": str})
    
    df["sigungu_code"] = df["코드"].str[:5]
    
    total_cols = [c for c in df.columns if c.startswith("계_")]
    elderly_cols = []
    for col in total_cols:
        age_str = col.replace("계_", "").replace("세", "").replace(" 이상", "")
        if age_str.isdigit() and int(age_str) >= 65:
            elderly_cols.append(col)
        elif age_str == "100":
            elderly_cols.append(col)
            
    df["전체인구"] = df[total_cols].sum(axis=1)
    df["고령인구"] = df[elderly_cols].sum(axis=1)
    
    sigungu_df = df.groupby(["연도", "sigungu_code"]).agg({
        "시도": "first",
        "시군구": "first",
        "전체인구": "sum",
        "고령인구": "sum"
    }).reset_index()
    
    sigungu_df["고령화율"] = (sigungu_df["고령인구"] / sigungu_df["전체인구"]) * 100
    sigungu_df["고령화율"] = sigungu_df["고령화율"].round(1)
    
    sigungu_df["시도"] = sigungu_df["시도"].fillna("")
    sigungu_df["시군구"] = sigungu_df["시군구"].fillna("")
    sigungu_df["지역명"] = (sigungu_df["시도"] + " " + sigungu_df["시군구"]).str.strip()
    
    bins = [0, 19, 23, 28, 38, 100]
    labels = ["19% 미만", "19% 이상 ~ 23% 미만", "23% 이상 ~ 28% 미만", "28% 이상 ~ 38% 미만", "38% 이상"]
    sigungu_df["고령화 구간"] = pd.cut(sigungu_df["고령화율"], bins=bins, labels=labels, right=False)
    
    sigungu_df["전국순위"] = sigungu_df.groupby("연도")["고령화율"].rank(ascending=False, method="min").astype(int)
    
    latest_year = int(sigungu_df["연도"].max())
    return sigungu_df, latest_year

@st.cache_data
def load_geojson():
    """시군구 GeoJSON 경계 데이터 및 중심 좌표를 계산해 불러옵니다."""
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(geojson_url)
    geojson = response.json()
    
    centers = {}
    for feature in geojson["features"]:
        code = feature["properties"]["코드"]
        geom = feature["geometry"]
        coords = []
        if geom["type"] == "Polygon":
            coords = geom["coordinates"][0]
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                coords.extend(poly[0])
        if coords:
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            centers[code] = (np.mean(lats), np.mean(lons))
            
    return geojson, centers

sigungu_yearly, max_year = load_population_data()
geojson_data, geo_centers = load_geojson()
min_year = int(sigungu_yearly["연도"].min())

# ==========================================
# 3. 사이드바 컨트롤
# ==========================================
st.sidebar.markdown("### ⚙️ 컨트롤 파넬")

selected_year = st.sidebar.slider(
    "📅 지도 연도 선택",
    min_value=min_year,
    max_value=max_year,
    value=max_year,
    step=1
)

valid_regions = [r for r in sigungu_yearly["지역명"].dropna().unique() if r]
all_regions = ["전국 (전체)"] + sorted(valid_regions)

selected_region = st.sidebar.selectbox(
    "🔍 분석 지자체 타겟팅",
    options=all_regions,
    index=0
)

df_year = sigungu_yearly[sigungu_yearly["연도"] == selected_year].copy()

# ==========================================
# 4. 상단 KPI 커스텀 카드 영역
# ==========================================
nat_total_pop = df_year["전체인구"].sum()
nat_elderly_pop = df_year["고령인구"].sum()
nat_aging_rate = round((nat_elderly_pop / nat_total_pop) * 100, 1)

super_aged_count = len(df_year[df_year["고령화율"] >= 20.0])
super_aged_ratio = round((super_aged_count / len(df_year)) * 100, 1)

top_region_row = df_year.sort_values(by="고령화율", ascending=False).iloc[0]
bottom_region_row = df_year.sort_values(by="고령화율", ascending=True).iloc[0]

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(f'''
    <div class="kpi-card">
        <div class="kpi-title">🌐 전국 평균 고령화율 ({selected_year}년)</div>
        <div class="kpi-value">{nat_aging_rate}%</div>
        <div class="kpi-sub">총 인구 {nat_total_pop:,}명 기준</div>
    </div>
    ''', unsafe_allow_html=True)

with k2:
    st.markdown(f'''
    <div class="kpi-card">
        <div class="kpi-title">🚨 초고령 지자체 (20% 이상)</div>
        <div class="kpi-value">{super_aged_count}개</div>
        <div class="kpi-sub" style="color:#ef4444;">전국 시군구의 {super_aged_ratio}%</div>
    </div>
    ''', unsafe_allow_html=True)

with k3:
    st.markdown(f'''
    <div class="kpi-card">
        <div class="kpi-title">🔴 최고 고령화 지역</div>
        <div class="kpi-value">{top_region_row["고령화율"]}%</div>
        <div class="kpi-sub" style="color:#dc2626;">{top_region_row["지역명"]}</div>
    </div>
    ''', unsafe_allow_html=True)

with k4:
    st.markdown(f'''
    <div class="kpi-card">
        <div class="kpi-title">🔵 최저 고령화 지역</div>
        <div class="kpi-value">{bottom_region_row["고령화율"]}%</div>
        <div class="kpi-sub" style="color:#2563eb;">{bottom_region_row["지역명"]}</div>
    </div>
    ''', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 5. 메인 대시보드 탭 구성
# ==========================================
tab_main, tab_treemap, tab_timelapse, tab_dday, tab_rank = st.tabs([
    "🗺️ 지도 & 미래 예측", 
    "🔲 시도별 인터랙티브 트리맵",
    "🎞️ 10년 고령화 타임랩스", 
    "🚨 초고령사회 진입 D-Day", 
    "🏎️ 순위 변동 & 가속도"
])

# ------------------------------------------
# TAB 1: 지도 및 미래 예측
# ------------------------------------------
with tab_main:
    col_map, col_chart = st.columns([1.1, 0.9])

    with col_map:
        st.markdown(f"#### 🗺️ {selected_year}년 전국 시군구 고령화 지도")

        color_discrete_map = {
            "19% 미만": "#e0f2fe",
            "19% 이상 ~ 23% 미만": "#7dd3fc",
            "23% 이상 ~ 28% 미만": "#38bdf8",
            "28% 이상 ~ 38% 미만": "#0284c7",
            "38% 이상": "#0369a1"
        }

        fig_map = px.choropleth_mapbox(
            df_year,
            geojson=geojson_data,
            locations="sigungu_code",
            featureidkey="properties.코드",
            color="고령화 구간",
            color_discrete_map=color_discrete_map,
            category_orders={"고령화 구간": ["19% 미만", "19% 이상 ~ 23% 미만", "23% 이상 ~ 28% 미만", "28% 이상 ~ 38% 미만", "38% 이상"]},
            hover_name="지역명",
            hover_data={"시도": True, "시군구": True, "고령화율": ":.1f%", "sigungu_code": False, "고령화 구간": False},
            center={"lat": 35.8, "lon": 127.8},
            zoom=6.0,
            mapbox_style="white-bg"
        )

        if selected_region != "전국 (전체)":
            selected_row = df_year[df_year["지역명"] == selected_region]
            if len(selected_row) > 0:
                target_code = selected_row.iloc[0]["sigungu_code"]
                if target_code in geo_centers:
                    lat, lon = geo_centers[target_code]
                    fig_map.add_trace(go.Scattermapbox(
                        lat=[lat],
                        lon=[lon],
                        mode="markers+text",
                        marker=dict(size=14, color="#ef4444"),
                        text=[f"📍 {selected_region}"],
                        textposition="top center",
                        name="선택 지역"
                    ))
                    fig_map.update_layout(mapbox=dict(center=dict(lat=lat, lon=lon), zoom=8.0))

        fig_map.update_layout(
            margin={"r":0, "t":10, "l":0, "b":0}, 
            height=530,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_map, use_container_width=True)

    with col_chart:
        st.markdown("#### 🔮 2035년 미래 고령화율 예측")

        if selected_region != "전국 (전체)":
            reg_df = sigungu_yearly[sigungu_yearly["지역명"] == selected_region].sort_values("연도")
            
            X = reg_df["연도"].values
            y = reg_df["고령화율"].values
            poly = np.polyfit(X, y, 1)
            
            future_years = np.arange(max_year + 1, 2036)
            future_y = np.polyval(poly, future_years).round(1)

            fig_pred = go.Figure()
            fig_pred.add_trace(go.Scatter(
                x=X, y=y, mode="lines+markers", name="관측치",
                line=dict(color="#3b82f6", width=3)
            ))
            fig_pred.add_trace(go.Scatter(
                x=np.append(X[-1], future_years), y=np.append(y[-1], future_y),
                mode="lines+markers", name="예측치",
                line=dict(color="#f43f5e", width=3, dash="dot")
            ))

            pred_2035 = future_y[-1]
            st.success(f"📍 **{selected_region} 분석 카드**\n- 현재 ({max_year}년): **{y[-1]}%**\n- 2035년 예상: **{pred_2035}%** (`+{round(pred_2035 - y[-1], 1)}%p` 증가 예상)")

            fig_pred.update_layout(
                xaxis=dict(title="연도", dtick=2),
                yaxis=dict(title="고령화율 (%)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin={"r":10, "t":10, "l":10, "b":10},
                height=400,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_pred, use_container_width=True)
        else:
            st.info("👈 사이드바 필터에서 특정 **시군구**를 선택하시면 2035년 시점까지의 인구 고령화 트렌드 예측 그래프를 볼 수 있습니다.")

# ------------------------------------------
# TAB 2: 트리맵 (Treemap)
# ------------------------------------------
with tab_treemap:
    st.markdown(f"#### 🔲 {selected_year}년 시·도 및 시군구 인구 계층 트리맵")
    st.caption("네모 박스를 클릭하면 원하는 시·도 내부의 시군구 구조로 계층 이동이 가능합니다.")

    fig_tree = px.treemap(
        df_year,
        path=[px.Constant("전국"), "시도", "시군구"],
        values="전체인구",
        color="고령화율",
        color_continuous_scale="Reds",
        range_color=[10, 45],
        hover_data={"고령화율": ":.1f%", "전체인구": ":,명", "고령인구": ":,명"}
    )
    fig_tree.update_layout(margin={"r":0, "t":30, "l":0, "b":0}, height=580)
    st.plotly_chart(fig_tree, use_container_width=True)

# ------------------------------------------
# TAB 3: 타임랩스 애니메이션
# ------------------------------------------
with tab_timelapse:
    st.markdown("#### 🎞️ 2015~2026 고령화 시계열 애니메이션")
    st.caption("재생 버튼(▶)을 누르면 전국의 고령화 진행속도를 다이나믹하게 시각화합니다.")

    fig_anim = px.choropleth_mapbox(
        sigungu_yearly.sort_values("연도"),
        geojson=geojson_data,
        locations="sigungu_code",
        featureidkey="properties.코드",
        color="고령화율",
        color_continuous_scale="Reds",
        range_color=[10, 45],
        animation_frame="연도",
        hover_name="지역명",
        hover_data={"시도": True, "시군구": True, "고령화율": ":.1f%", "sigungu_code": False},
        center={"lat": 35.8, "lon": 127.8},
        zoom=6.0,
        mapbox_style="white-bg"
    )
    fig_anim.update_layout(margin={"r":0, "t":10, "l":0, "b":0}, height=580)
    st.plotly_chart(fig_anim, use_container_width=True)

# ------------------------------------------
# TAB 4: 초고령사회 진입 D-Day
# ------------------------------------------
with tab_dday:
    st.markdown("#### 🚨 지자체별 초고령사회(20%) 진입 분석 카드")

    dday_list = []
    for reg, grp in sigungu_yearly.groupby("지역명"):
        grp = grp.sort_values("연도")
        super_aged = grp[grp["고령화율"] >= 20.0]
        
        if len(super_aged) > 0:
            first_entry_year = int(super_aged.iloc[0]["연도"])
            status = f"✅ {first_entry_year}년 진입"
            d_day = first_entry_year - max_year
        else:
            X = grp["연도"].values
            y = grp["고령화율"].values
            poly = np.polyfit(X, y, 1)
            if poly[0] > 0:
                est_year = int((20.0 - poly[1]) / poly[0])
                status = f"⏳ {est_year}년 진입 예정"
                d_day = est_year - max_year
            else:
                status = "🟢 유지 예상"
                d_day = 999
                
        curr_rate_series = grp[grp["연도"] == max_year]["고령화율"]
        if not curr_rate_series.empty:
            curr_rate = curr_rate_series.values[0]
        else:
            curr_rate = grp.iloc[-1]["고령화율"]

        dday_list.append({
            "지역명": reg,
            f"{max_year}년 고령화율": f"{curr_rate}%",
            "상태": status,
            "D-Day (연)": d_day if d_day != 999 else "-"
        })

    df_dday = pd.DataFrame(dday_list)

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("##### 🔴 초고령사회 진입 완료 지자체")
        st.dataframe(df_dday[df_dday["상태"].str.contains("진입") & ~df_dday["상태"].str.contains("예정")].reset_index(drop=True), use_container_width=True)

    with col_d2:
        st.markdown("##### ⏳ 초고령사회 진입 임박 지자체 (미래 진입)")
        st.dataframe(df_dday[df_dday["상태"].str.contains("예정")].sort_values("D-Day (연)").reset_index(drop=True), use_container_width=True)

# ------------------------------------------
# TAB 5: 순위 변동 & 가속도
# ------------------------------------------
with tab_rank:
    st.markdown("#### 🏎️ 10년 고령화 순위 급상승 & 가속도 분석")
    
    df_min = sigungu_yearly[sigungu_yearly["연도"] == min_year][["sigungu_code", "지역명", "고령화율", "전국순위"]]
    df_max = sigungu_yearly[sigungu_yearly["연도"] == max_year][["sigungu_code", "고령화율", "전국순위"]]

    rank_diff = pd.merge(df_min, df_max, on="sigungu_code", suffixes=(f"_{min_year}", f"_{max_year}"))

    rank_diff["순위 상승폭 (계단)"] = rank_diff[f"전국순위_{min_year}"] - rank_diff[f"전국순위_{max_year}"]
    rank_diff["고령화율 증가폭 (%p)"] = (rank_diff[f"고령화율_{max_year}"] - rank_diff[f"고령화율_{min_year}"]).round(1)

    rank_diff = rank_diff[[
        "지역명", 
        f"고령화율_{min_year}", 
        f"고령화율_{max_year}", 
        f"전국순위_{min_year}", 
        f"전국순위_{max_year}", 
        "순위 상승폭 (계단)", 
        "고령화율 증가폭 (%p)"
    ]]
    rank_diff.columns = [
        "지역명", 
        f"{min_year}년 고령화율", 
        f"{max_year}년 고령화율", 
        f"{min_year}년 순위", 
        f"{max_year}년 순위", 
        "순위 상승폭 (계단)", 
        "고령화율 증가폭 (%p)"
    ]

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown("##### 📈 고령화 순위가 가장 급상승한 지역")
        st.dataframe(rank_diff.sort_values(by="순위 상승폭 (계단)", ascending=False).head(10).reset_index(drop=True), use_container_width=True)

    with col_r2:
        st.markdown("##### ⚡ 고령화 속도(%p)가 가장 빠른 지역")
        st.dataframe(rank_diff.sort_values(by="고령화율 증가폭 (%p)", ascending=False).head(10).reset_index(drop=True), use_container_width=True)

# ==========================================
# 6. 하단 요약 데이터 카드
# ==========================================
st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown(f"### 📋 {selected_year}년 고령화율 극단 지역 (Top 10 / Bottom 10)")

col1, col2 = st.columns(2)

top10_simple = (
    df_year.sort_values(by="고령화율", ascending=False)
    .head(10)[["지역명", "고령화율"]]
    .reset_index(drop=True)
)
top10_simple.index = top10_simple.index + 1
top10_simple.columns = ["지역명", "고령화율 (%)"]

bottom10_simple = (
    df_year.sort_values(by="고령화율", ascending=True)
    .head(10)[["지역명", "고령화율"]]
    .reset_index(drop=True)
)
bottom10_simple.index = bottom10_simple.index + 1
bottom10_simple.columns = ["지역명", "고령화율 (%)"]

with col1:
    st.markdown("🔴 **고령화율 상위 10개 지역**")
    st.dataframe(top10_simple, use_container_width=True)

with col2:
    st.markdown("🔵 **고령화율 하위 10개 지역**")
    st.dataframe(bottom10_simple, use_container_width=True)
