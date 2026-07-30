import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components

# ==========================================
# 1. 페이지 설정 및 트렌디 대시보드 CSS
# ==========================================
st.set_page_config(
    page_title="대한민국 고령화 인사이더 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 모던 스타일링 CSS
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    * {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
    
    .stApp {
        background-color: #f8fafc;
    }
    
    /* 대시보드 헤더 */
    .dashboard-header {
        background: #ffffff;
        padding: 24px 32px;
        border-radius: 20px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        margin-bottom: 24px;
    }
    
    .header-title {
        font-size: 1.8rem;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.5px;
    }
    
    .header-sub {
        font-size: 0.95rem;
        color: #64748b;
        margin-top: 4px;
    }
    
    /* 모던 KPI 카드 */
    .kpi-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02);
    }
    .kpi-label {
        font-size: 0.8rem;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-val {
        font-size: 1.9rem;
        font-weight: 800;
        color: #0f172a;
        margin: 6px 0;
    }
    .kpi-desc {
        font-size: 0.8rem;
        font-weight: 600;
        color: #3b82f6;
    }

    /* 탭 스타일 개편 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #cbd5e1;
        padding: 6px;
        border-radius: 14px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 0.95rem;
        color: #475569;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }
</style>
""", unsafe_allow_html=True)

# 헤더 영역
st.markdown("""
<div class="dashboard-header">
    <div class="header-title">📊 대한민국 고령화 인사이더 대시보드</div>
    <div class="header-sub">전국 시군구 인구 구조 분석 · 타겟 지역 딥다이브 진단 · 종합 브리핑 보고서</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 2. 데이터 처리 (행정구역 명칭 표준화 반영)
# ==========================================
@st.cache_data
def load_population_data():
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(pop_url, dtype={"코드": str})
    
    df["sigungu_code"] = df["코드"].str[:5]
    
    # 시도 명칭 변경(강원특별자치도 등)에 따른 매칭 불일치 완화를 위해 표준화 처리
    df["시도"] = df["시도"].fillna("").astype(str)
    df["시군구"] = df["시군구"].fillna("").astype(str)
    
    # 연도별로 명칭이 다를 수 있어 코드를 대표 명칭으로 통일
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
    
    # 코드를 기준으로 시도, 시군구의 가장 최근 명칭 추출해서 통일
    latest_names = df.sort_values("연도").groupby("sigungu_code").last()[["시도", "시군구"]].reset_index()
    latest_names.columns = ["sigungu_code", "표준시도", "표준시군구"]
    
    df = pd.merge(df, latest_names, on="sigungu_code", how="left")
    
    sigungu_df = df.groupby(["연도", "sigungu_code"]).agg({
        "표준시도": "first",
        "표준시군구": "first",
        "전체인구": "sum",
        "고령인구": "sum"
    }).reset_index()
    
    sigungu_df.rename(columns={"표준시도": "시도", "표준시군구": "시군구"}, inplace=True)
    
    sigungu_df["고령화율"] = (sigungu_df["고령인구"] / sigungu_df["전체인구"]) * 100
    sigungu_df["고령화율"] = sigungu_df["고령화율"].round(1)
    
    sigungu_df["지역명"] = (sigungu_df["시도"] + " " + sigungu_df["시군구"]).str.strip()
    
    bins = [0, 19, 23, 28, 38, 100]
    labels = ["19% 미만", "19% 이상 ~ 23% 미만", "23% 이상 ~ 28% 미만", "28% 이상 ~ 38% 미만", "38% 이상"]
    sigungu_df["고령화 구간"] = pd.cut(sigungu_df["고령화율"], bins=bins, labels=labels, right=False)
    
    sigungu_df["전국순위"] = sigungu_df.groupby("연도")["고령화율"].rank(ascending=False, method="min").astype(int)
    
    latest_year = int(sigungu_df["연도"].max())
    return sigungu_df, latest_year

@st.cache_data
def load_geojson():
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    res = requests.get(geojson_url)
    geojson = res.json()
    
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
# 3. 사이드바 검색 컨트롤
# ==========================================
st.sidebar.markdown("### ⚙️ 대시보드 제어판")

selected_year = st.sidebar.slider(
    "📅 데이터 분석 연도",
    min_value=min_year,
    max_value=max_year,
    value=max_year,
    step=1
)

valid_regions = [r for r in sigungu_yearly["지역명"].dropna().unique() if r]
all_regions = ["전국 (전체)"] + sorted(valid_regions)

selected_region = st.sidebar.selectbox(
    "🔍 타겟 시군구 검색 (개별 진단)",
    options=all_regions,
    index=0
)

df_year = sigungu_yearly[sigungu_yearly["연도"] == selected_year].copy()

# 데이터 다운로드 파트
st.sidebar.markdown("---")
st.sidebar.markdown("### 📥 데이터 다운로드")

csv_year_data = df_year[["연도", "시도", "시군구", "지역명", "전체인구", "고령인구", "고령화율", "전국순위"]].to_csv(index=False).encode('utf-8-sig')
st.sidebar.download_button(
    label=f"📊 {selected_year}년 전국 시군구 CSV 받기",
    data=csv_year_data,
    file_name=f"korea_aging_{selected_year}.csv",
    mime="text/csv"
)

if selected_region != "전국 (전체)":
    reg_history_df = sigungu_yearly[sigungu_yearly["지역명"] == selected_region][["연도", "시도", "시군구", "전체인구", "고령인구", "고령화율", "전국순위"]].sort_values("연도")
    csv_reg_data = reg_history_df.to_csv(index=False).encode('utf-8-sig')
    st.sidebar.download_button(
        label=f"💾 {selected_region} 10년 추이 CSV 받기",
        data=csv_reg_data,
        file_name=f"{selected_region}_history.csv",
        mime="text/csv"
    )

# ==========================================
# 4. 상단 KPI 요약 카드 (전국 공통)
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
    <div class="kpi-box">
        <div class="kpi-label">전국 평균 고령화율 ({selected_year}년)</div>
        <div class="kpi-val">{nat_aging_rate}%</div>
        <div class="kpi-desc">전체인구 {nat_total_pop:,}명</div>
    </div>
    ''', unsafe_allow_html=True)

with k2:
    st.markdown(f'''
    <div class="kpi-box">
        <div class="kpi-label">초고령 지자체 (20%↑)</div>
        <div class="kpi-val">{super_aged_count}곳</div>
        <div class="kpi-desc" style="color:#ef4444;">전국 지자체의 {super_aged_ratio}%</div>
    </div>
    ''', unsafe_allow_html=True)

with k3:
    st.markdown(f'''
    <div class="kpi-box">
        <div class="kpi-label">최고 고령화 지자체</div>
        <div class="kpi-val">{top_region_row["고령화율"]}%</div>
        <div class="kpi-desc" style="color:#dc2626;">{top_region_row["지역명"]}</div>
    </div>
    ''', unsafe_allow_html=True)

with k4:
    st.markdown(f'''
    <div class="kpi-box">
        <div class="kpi-label">최저 고령화 지자체</div>
        <div class="kpi-val">{bottom_region_row["고령화율"]}%</div>
        <div class="kpi-desc" style="color:#2563eb;">{bottom_region_row["지역명"]}</div>
    </div>
    ''', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# SECTION 1: 🌐 전국 단위 빅데이터 분석 (항상 표시)
# ==========================================
st.markdown("### 🌐 PART 1. 대한민국 전체 고령화 지형도")

tab_map, tab_infra, tab_scatter, tab_tree = st.tabs([
    "🗺️ 전국 단계구분도", 
    "🏥 복지 인프라 공급 시급성",
    "🎯 고령인구 규모 vs 비율 매트릭스",
    "🔲 시·도 계층별 트리맵"
])

# ------------------------------------------
# TAB 1: 지도
# ------------------------------------------
with tab_map:
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
                    name="선택 지자체"
                ))
                fig_map.update_layout(mapbox=dict(center=dict(lat=lat, lon=lon), zoom=8.0))

    fig_map.update_layout(margin={"r":0, "t":10, "l":0, "b":0}, height=550)
    st.plotly_chart(fig_map, use_container_width=True)

# ------------------------------------------
# TAB 2: 복지 인프라 분석
# ------------------------------------------
with tab_infra:
    avg_elderly_pop = df_year["고령인구"].median()
    avg_aging_rate = df_year["고령화율"].mean()

    def classify_infra(row):
        if row["고령화율"] >= avg_aging_rate and row["고령인구"] >= avg_elderly_pop:
            return "🚨 1순위: 시설 확충 최우선 (고비율+대규모)"
        elif row["고령인구"] >= avg_elderly_pop:
            return "⚠️ 2순위: 거점 복지시설 필요 (대규모 인구)"
        elif row["고령화율"] >= avg_aging_rate:
            return "🟡 3순위: 방문/이동형 케어 필요 (고비율 소규모)"
        else:
            return "🟢 4순위: 일반 관리 지역"

    df_year["인프라시급성"] = df_year.apply(classify_infra, axis=1)
    infra_counts = df_year["인프라시급성"].value_counts()

    col_i1, col_i2 = st.columns([1, 1])

    with col_i1:
        st.markdown("##### 📌 지자체 인프라 시급성 비율 현황")
        fig_infra_pie = px.pie(
            names=infra_counts.index,
            values=infra_counts.values,
            color=infra_counts.index,
            color_discrete_map={
                "🚨 1순위: 시설 확충 최우선 (고비율+대규모)": "#ef4444",
                "⚠️ 2순위: 거점 복지시설 필요 (대규모 인구)": "#f97316",
                "🟡 3순위: 방문/이동형 케어 필요 (고비율 소규모)": "#eab308",
                "🟢 4순위: 일반 관리 지역": "#22c55e"
            },
            hole=0.4
        )
        fig_infra_pie.update_layout(height=380, margin={"r":10, "t":10, "l":10, "b":10})
        st.plotly_chart(fig_infra_pie, use_container_width=True)

    with col_i2:
        st.markdown("##### 🚨 1순위 확충 최우선 지자체 Top 10")
        p1_df = df_year[df_year["인프라시급성"].str.contains("1순위")].sort_values(by="고령인구", ascending=False).head(10)
        p1_display = p1_df[["지역명", "고령인구", "고령화율"]].reset_index(drop=True)
        p1_display.columns = ["지역명", "65세 이상 인구 (명)", "고령화율 (%)"]
        st.dataframe(p1_display, use_container_width=True)

# ------------------------------------------
# TAB 3: 버블 산점도 분석
# ------------------------------------------
with tab_scatter:
    avg_rate = df_year["고령화율"].mean()

    fig_bubble = px.scatter(
        df_year,
        x="고령인구",
        y="고령화율",
        size="전체인구",
        color="시도",
        hover_name="지역명",
        hover_data={"전체인구": ":,명", "고령인구": ":,명", "고령화율": ":.1f%"},
        log_x=True,
        labels={"고령인구": "65세 이상 인구수 (명, 로그 스케일)", "고령화율": "고령화 비율 (%)"}
    )

    fig_bubble.add_hline(y=avg_rate, line_dash="dash", line_color="red", annotation_text=f"전국 평균 비율 ({avg_rate:.1f}%)")
    fig_bubble.update_layout(height=550, margin={"r":10, "t":30, "l":10, "b":10})
    st.plotly_chart(fig_bubble, use_container_width=True)

# ------------------------------------------
# TAB 4: 시도 트리맵
# ------------------------------------------
with tab_tree:
    fig_tree = px.treemap(
        df_year,
        path=[px.Constant("전국"), "시도", "시군구"],
        values="전체인구",
        color="고령화율",
        color_continuous_scale="Reds",
        range_color=[10, 45],
        hover_data={"고령화율": ":.1f%", "전체인구": ":,명", "고령인구": ":,명"}
    )
    fig_tree.update_layout(margin={"r":0, "t":30, "l":0, "b":0}, height=550)
    st.plotly_chart(fig_tree, use_container_width=True)

# 하단 간단 극단 지자체 표
col_t1, col_t2 = st.columns(2)
top10 = df_year.sort_values(by="고령화율", ascending=False).head(10)[["지역명", "고령화율"]].reset_index(drop=True)
top10.index = top10.index + 1
top10.columns = ["지역명", "고령화율 (%)"]

bottom10 = df_year.sort_values(by="고령화율", ascending=True).head(10)[["지역명", "고령화율"]].reset_index(drop=True)
bottom10.index = bottom10.index + 1
bottom10.columns = ["지역명", "고령화율 (%)"]

with col_t1:
    st.markdown("🔴 **고령화율 가장 높은 지역 Top 10**")
    st.dataframe(top10, use_container_width=True)

with col_t2:
    st.markdown("🔵 **고령화율 가장 낮은 지역 Top 10**")
    st.dataframe(bottom10, use_container_width=True)


# ==========================================
# SECTION 2: 🔍 타겟 지자체 딥다이브 (지역 선택시에만 노출)
# ==========================================
if selected_region != "전국 (전체)":
    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.markdown(f"### 🔍 PART 2. 타겟 지자체 딥다이브 분석 — [{selected_region}]")

    target_match = df_year[df_year["지역명"] == selected_region]

    if not target_match.empty:
        rep_row = target_match.iloc[0]
        
        reg_df = sigungu_yearly[sigungu_yearly["지역명"] == selected_region].sort_values("연도")
        X = reg_df["연도"].values
        y = reg_df["고령화율"].values
        poly = np.polyfit(X, y, 1)
        future_years = np.arange(max_year + 1, 2036)
        future_y = np.polyval(poly, future_years).round(1)

        curr_rate = y[-1]
        pred_2035 = future_y[-1]
        growth_10y = round(curr_rate - y[0], 1) if len(y) > 0 else 0.0

        sub_tab1, sub_tab2, sub_tab3 = st.tabs([
            "🩺 위험 등급 진단 & 2035년 예측",
            "⚔️ 1:1 타 지자체 교차 비교",
            "📑 브리핑 보고서 (PDF/인쇄 생성)"
        ])

        with sub_tab1:
            col_pred1, col_pred2 = st.columns([1, 1])

            with col_pred1:
                st.markdown("##### 🚨 고령화 위험 등급 진단")
                if curr_rate >= 30.0:
                    st.error(f"**[초고위험 단계]**\n\n**{selected_region}**은(는) 고령화율이 **{curr_rate}%**로 심각한 초고령사회 수준입니다. 사회적 복지 비용 폭증에 대한 신속한 정책 마련이 시급합니다.")
                elif curr_rate >= 20.0:
                    st.warning(f"**[고위험 단계 - 초고령사회]**\n\n**{selected_region}**은(는) 고령화율 **{curr_rate}%**로 UN 기준 초고령사회에 해당합니다. (지난 10년간 **+{growth_10y}%p** 증가)")
                elif curr_rate >= 14.0:
                    st.info(f"**[주의 단계 - 고령사회]**\n\n**{selected_region}**은(는) 현재 고령사회이며, 2035년에는 **{pred_2035}%**에 도달할 것으로 예상됩니다.")
                else:
                    st.success(f"**[양호 단계]**\n\n**{selected_region}**은(는) 고령화율 **{curr_rate}%**로 비교적 젊은 인구 체질을 유지하고 있습니다.")

                if "인프라시급성" in rep_row:
                    st.info(f"🏥 **복지 인프라 공급 유형:** `{rep_row['인프라시급성']}`")

            with col_pred2:
                st.markdown("##### 🔮 2035년 시점 미래 추이 예측")
                fig_pred = go.Figure()
                fig_pred.add_trace(go.Scatter(x=X, y=y, mode="lines+markers", name="관측치", line=dict(color="#3b82f6", width=3)))
                fig_pred.add_trace(go.Scatter(x=np.append(X[-1], future_years), y=np.append(y[-1], future_y), mode="lines+markers", name="예측치", line=dict(color="#ef4444", width=3, dash="dot")))
                fig_pred.update_layout(
                    xaxis=dict(title="연도", dtick=2), yaxis=dict(title="고령화율 (%)"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin={"r":10, "t":10, "l":10, "b":10}, height=300
                )
                st.plotly_chart(fig_pred, use_container_width=True)

        with sub_tab2:
            st.markdown(f"##### ⚔️ [{selected_region}] VS 다른 지자체 1:1 비교")
            region_list_sub = sorted([r for r in valid_regions if r != selected_region])
            
            region_B = st.selectbox("🔴 비교할 상대 지자체 선택", options=region_list_sub, index=0)

            if region_B:
                df_A = rep_row
                df_B_match = df_year[df_year["지역명"] == region_B]
                
                if not df_B_match.empty:
                    df_B = df_B_match.iloc[0]

                    c_kpi1, c_kpi2 = st.columns(2)
                    with c_kpi1:
                        st.info(f"**🔵 {selected_region}**\n- 고령화율: `{df_A['고령화율']}%` (전국 {df_A['전국순위']}위)\n- 전체인구: `{df_A['전체인구']:,}명` | 고령인구: `{df_A['고령인구']:,}명`")
                    with c_kpi2:
                        st.warning(f"**🔴 {region_B}**\n- 고령화율: `{df_B['고령화율']}%` (전국 {df_B['전국순위']}위)\n- 전체인구: `{df_B['전체인구']:,}명` | 고령인구: `{df_B['고령인구']:,}명`")

                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        trend_A = sigungu_yearly[sigungu_yearly["지역명"] == selected_region].sort_values("연도")
                        trend_B = sigungu_yearly[sigungu_yearly["지역명"] == region_B].sort_values("연도")
                        
                        fig_comp_line = go.Figure()
                        fig_comp_line.add_trace(go.Scatter(x=trend_A["연도"], y=trend_A["고령화율"], mode="lines+markers", name=f"🔵 {selected_region}", line=dict(color="#2563eb", width=3)))
                        fig_comp_line.add_trace(go.Scatter(x=trend_B["연도"], y=trend_B["고령화율"], mode="lines+markers", name=f"🔴 {region_B}", line=dict(color="#ef4444", width=3)))
                        fig_comp_line.update_layout(xaxis=dict(title="연도"), yaxis=dict(title="고령화율 (%)"), margin={"r":10, "t":10, "l":10, "b":10}, height=320)
                        st.plotly_chart(fig_comp_line, use_container_width=True)

                    with col_c2:
                        comp_pop_df = pd.DataFrame({
                            "구분": ["전체 인구", "65세 이상 인구"],
                            f"🔵 {selected_region}": [df_A["전체인구"], df_A["고령인구"]],
                            f"🔴 {region_B}": [df_B["전체인구"], df_B["고령인구"]]
                        })
                        fig_comp_bar = px.bar(comp_pop_df, x="구분", y=[f"🔵 {selected_region}", f"🔴 {region_B}"], barmode="group", color_discrete_sequence=["#2563eb", "#ef4444"])
                        fig_comp_bar.update_layout(yaxis=dict(title="인원수 (명)"), margin={"r":10, "t":10, "l":10, "b":10}, height=320)
                        st.plotly_chart(fig_comp_bar, use_container_width=True)

        with sub_tab3:
            st.markdown("##### 📑 한 클릭 종합 브리핑 보고서")
            
            rate_2015 = reg_df.iloc[0]["고령화율"] if len(reg_df) > 0 else 0.0
            rate_curr = rep_row["고령화율"]
            diff_rate = round(rate_curr - rate_2015, 1)

            report_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: 'Malgun Gothic', sans-serif; padding: 15px; background: #fff; color: #333; }}
                    .rep-card {{ border: 2px solid #0f172a; border-radius: 12px; padding: 25px; max-width: 750px; margin: 0 auto; }}
                    .rep-title {{ font-size: 22px; font-weight: bold; border-bottom: 3px solid #2563eb; padding-bottom: 10px; margin-bottom: 15px; text-align: center; color: #0f172a; }}
                    .rep-grid {{ display: flex; justify-content: space-between; margin-bottom: 15px; background: #f8fafc; padding: 12px; border-radius: 8px; }}
                    .rep-item {{ text-align: center; width: 30%; }}
                    .rep-label {{ font-size: 12px; color: #64748b; font-weight: bold; }}
                    .rep-val {{ font-size: 18px; font-weight: bold; color: #1e293b; margin-top: 4px; }}
                    .rep-section {{ margin-top: 15px; line-height: 1.6; font-size: 13px; }}
                    .print-btn {{ background: #2563eb; color: white; border: none; padding: 10px 20px; font-size: 14px; font-weight: bold; border-radius: 6px; cursor: pointer; margin-top: 15px; width: 100%; }}
                    .print-btn:hover {{ background: #1d4ed8; }}
                </style>
            </head>
            <body>
                <div class="rep-card">
                    <div class="rep-title">📄 {selected_region} 고령화 종합 브리핑 리포트</div>
                    <div class="rep-grid">
                        <div class="rep-item"><div class="rep-label">분석 연도</div><div class="rep-val">{selected_year}년</div></div>
                        <div class="rep-item"><div class="rep-label">고령화율 (전국 순위)</div><div class="rep-val">{rep_row['고령화율']}% ({rep_row['전국순위']}위)</div></div>
                        <div class="rep-item"><div class="rep-label">65세 이상 인구</div><div class="rep-val">{rep_row['고령인구']:,} 명</div></div>
                    </div>
                    <div class="rep-section">
                        <h4>📌 핵심 동향</h4>
                        <ul>
                            <li><b>인구 현황:</b> 총 인구 <b>{rep_row['전체인구']:,}명</b> 중 고령층 <b>{rep_row['고령인구']:,}명</b> 도달.</li>
                            <li><b>10년 변화:</b> 2015년({rate_2015}%) 대비 {selected_year}년({rate_curr}%)으로 <b>+{diff_rate}%p</b> 변화.</li>
                        </ul>
                    </div>
                    <button class="print-btn" onclick="window.print()">🖨️ PDF / A4 즉시 인쇄하기</button>
                </div>
            </body>
            </html>
            """
            components.html(report_html, height=420)
    else:
        st.warning(f"선택하신 연도({selected_year}년)에 [{selected_region}]의 데이터가 존재하지 않습니다.")
else:
    st.info("💡 사이드바에서 특정 **시군구**를 선택하시면 지자체 개별 딥다이브 진단 및 1:1 비교, 보고서 인쇄 창이 생성됩니다.")
