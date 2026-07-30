import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go

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
        background-color: #f1f5f9;
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
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
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
        background-color: #e2e8f0;
        padding: 6px;
        border-radius: 14px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 0.95rem;
        color: #64748b;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    }
</style>
""", unsafe_allow_html=True)

# 헤더 영역
st.markdown("""
<div class="dashboard-header">
    <div class="header-title">📊 대한민국 고령화 인사이더 대시보드</div>
    <div class="header-sub">전국 시군구별 인구 구조 분석 · 2035 미래 예측 · 지자체 1:1 수치 비교 및 위험 등급 진단 리포트</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 2. 데이터 처리 (캐싱 적용)
# ==========================================
@st.cache_data
def load_population_data():
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
# 3. 사이드바 검색 컨트롤 및 다운로드 파트
# ==========================================
st.sidebar.markdown("### ⚙️ 분석 제어판")

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
    "🔍 타겟 시군구 검색",
    options=all_regions,
    index=0
)

df_year = sigungu_yearly[sigungu_yearly["연도"] == selected_year].copy()

# 데이터 다운로드 버튼 파트 (사이드바 하단)
st.sidebar.markdown("---")
st.sidebar.markdown("### 📥 데이터 다운로드")

# 1) 전체 연도 필터링 데이터 다운로드
csv_year_data = df_year[["연도", "시도", "시군구", "지역명", "전체인구", "고령인구", "고령화율", "전국순위"]].to_csv(index=False).encode('utf-8-sig')
st.sidebar.download_button(
    label=f"📊 {selected_year}년 전국 시군구 CSV 받기",
    data=csv_year_data,
    file_name=f"korea_aging_{selected_year}.csv",
    mime="text/csv"
)

# 2) 선택된 특정 지자체 10년 추이 데이터 다운로드
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
# 4. 상단 KPI 요약 카드리스트
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
        <div class="kpi-label">전국 평균 고령화율</div>
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
# 5. 메인 탭 구성
# ==========================================
tab_map, tab_compare, tab_scatter, tab_tree = st.tabs([
    "🗺️ 전국 지도 & 미래 예측", 
    "⚔️ 지자체 1:1 비교",
    "🎯 고령인구 규모 vs 비율 분석",
    "🔲 시·도 계층별 트리맵"
])

# ------------------------------------------
# TAB 1: 전국 지도 및 2035 예측 & 자동 진단 리포트
# ------------------------------------------
with tab_map:
    col_m, col_p = st.columns([1.1, 0.9])

    with col_m:
        st.markdown(f"##### 🗺️ {selected_year}년 전국 시군구 고령화 지도")

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

        fig_map.update_layout(margin={"r":0, "t":10, "l":0, "b":0}, height=530)
        st.plotly_chart(fig_map, use_container_width=True)

    with col_p:
        st.markdown("##### 🔮 고령화 진단 리포트 & 2035년 미래 예측")

        if selected_region != "전국 (전체)":
            reg_df = sigungu_yearly[sigungu_yearly["지역명"] == selected_region].sort_values("연도")
            
            X = reg_df["연도"].values
            y = reg_df["고령화율"].values
            poly = np.polyfit(X, y, 1)
            
            future_years = np.arange(max_year + 1, 2036)
            future_y = np.polyval(poly, future_years).round(1)

            curr_rate = y[-1]
            pred_2035 = future_y[-1]
            growth_10y = round(curr_rate - y[0], 1) if len(y) > 0 else 0.0

            # 고령화 위험 등급 자동 진단 로직
            if curr_rate >= 30.0:
                risk_level = "🚨 초고위험 단계"
                risk_color = "error"
                risk_msg = f"**{selected_region}**은(는) 고령화율이 **{curr_rate}%**로 이미 극심한 초고령사회에 진입해 있습니다. 복지 예산 부담 증대 및 유소년 인구 유출 대책이 시급합니다."
            elif curr_rate >= 20.0:
                risk_level = "⚠️ 고위험 단계 (초고령사회)"
                risk_color = "warning"
                risk_msg = f"**{selected_region}**은(는) UN 기준 초고령사회(20% 이상)에 해당하며, 지난 10년간 고령화율이 **+{growth_10y}%p** 증가하는 빠른 고령화 속도를 보이고 있습니다."
            elif curr_rate >= 14.0:
                risk_level = "🟡 주의 단계 (고령사회)"
                risk_color = "info"
                risk_msg = f"**{selected_region}**은(는) 고령사회(14% 이상) 수준에 도달해 있으며, 2035년경에는 **{pred_2035}%**까지 상승하여 초고령사회로 진입할 것으로 예상됩니다."
            else:
                risk_level = "🟢 양호 단계 (고령화사회 이하)"
                risk_color = "success"
                risk_msg = f"**{selected_region}**은(는) 고령화율이 **{curr_rate}%**로 전국 평균 대비 비교적 젊은 인구 구조를 유지하고 있습니다."

            # 진단 리포트 출력
            st.markdown(f"**[진단 결과: {risk_level}]**")
            if risk_color == "error":
                st.error(risk_msg)
            elif risk_color == "warning":
                st.warning(risk_msg)
            elif risk_color == "info":
                st.info(risk_msg)
            else:
                st.success(risk_msg)

            # 예측 그래프
            fig_pred = go.Figure()
            fig_pred.add_trace(go.Scatter(
                x=X, y=y, mode="lines+markers", name="관측치",
                line=dict(color="#3b82f6", width=3)
            ))
            fig_pred.add_trace(go.Scatter(
                x=np.append(X[-1], future_years), y=np.append(y[-1], future_y),
                mode="lines+markers", name="예측치",
                line=dict(color="#ef4444", width=3, dash="dot")
            ))

            fig_pred.update_layout(
                xaxis=dict(title="연도", dtick=2),
                yaxis=dict(title="고령화율 (%)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin={"r":10, "t":10, "l":10, "b":10},
                height=340
            )
            st.plotly_chart(fig_pred, use_container_width=True)
        else:
            st.info("👈 사이드바 필터에서 특정 **시군구**를 선택하시면 지자체 자동 진단 리포트와 2035년 미래 예측 그래프를 확인할 수 있습니다.")

# ------------------------------------------
# TAB 2: 지자체 1:1 비교
# ------------------------------------------
with tab_compare:
    st.markdown("##### ⚔️ 두 지자체 간 1:1 수치 및 추이 직접 비교")
    st.caption("비교하고 싶은 두 지자체를 자유롭게 선택하여 고령화율과 인구 규모를 다각도로 대조합니다.")

    col_sel1, col_sel2 = st.columns(2)
    region_list = sorted(valid_regions)
    
    default_idx1 = region_list.index("충청남도 공주시") if "충청남도 공주시" in region_list else 0
    default_idx2 = region_list.index("충청남도 아산시") if "충청남도 아산시" in region_list else min(1, len(region_list)-1)

    with col_sel1:
        region_A = st.selectbox("🔵 첫 번째 비교 지자체 (A)", options=region_list, index=default_idx1)
    with col_sel2:
        region_B = st.selectbox("🔴 두 번째 비교 지자체 (B)", options=region_list, index=default_idx2)

    if region_A and region_B:
        df_A = df_year[df_year["지역명"] == region_A].iloc[0]
        df_B = df_year[df_year["지역명"] == region_B].iloc[0]

        c_kpi1, c_kpi2 = st.columns(2)
        with c_kpi1:
            st.info(f"""
            **🔵 {region_A} ({selected_year}년 기준)**
            - **고령화율:** `{df_A['고령화율']}%` (전국 {df_A['전국순위']}위)
            - **전체 인구:** `{df_A['전체인구']:,}명`
            - **65세 이상 인구:** `{df_A['고령인구']:,}명`
            """)
        with c_kpi2:
            st.warning(f"""
            **🔴 {region_B} ({selected_year}년 기준)**
            - **고령화율:** `{df_B['고령화율']}%` (전국 {df_B['전국순위']}위)
            - **전체 인구:** `{df_B['전체인구']:,}명`
            - **65세 이상 인구:** `{df_B['고령인구']:,}명`
            """)

        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            st.markdown("##### 📈 연도별 고령화율 추이 비교 (%)")
            
            trend_A = sigungu_yearly[sigungu_yearly["지역명"] == region_A].sort_values("연도")
            trend_B = sigungu_yearly[sigungu_yearly["지역명"] == region_B].sort_values("연도")

            nat_trend = sigungu_yearly.groupby("연도").apply(
                lambda x: (x["고령인구"].sum() / x["전체인구"].sum()) * 100
            ).reset_index(name="전국평균")

            fig_comp_line = go.Figure()
            fig_comp_line.add_trace(go.Scatter(
                x=nat_trend["연도"], y=nat_trend["전국평균"].round(1),
                mode="lines", name="전국 평균", line=dict(color="#94a3b8", width=2, dash="dash")
            ))
            fig_comp_line.add_trace(go.Scatter(
                x=trend_A["연도"], y=trend_A["고령화율"],
                mode="lines+markers", name=f"🔵 {region_A}", line=dict(color="#2563eb", width=3)
            ))
            fig_comp_line.add_trace(go.Scatter(
                x=trend_B["연도"], y=trend_B["고령화율"],
                mode="lines+markers", name=f"🔴 {region_B}", line=dict(color="#ef4444", width=3)
            ))

            fig_comp_line.update_layout(
                xaxis=dict(title="연도", dtick=1),
                yaxis=dict(title="고령화율 (%)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin={"r":10, "t":10, "l":10, "b":10},
                height=380
            )
            st.plotly_chart(fig_comp_line, use_container_width=True)

        with col_c2:
            st.markdown(f"##### 📊 {selected_year}년 인구 구조 직접 비교 (명)")
            
            comp_pop_df = pd.DataFrame({
                "구분": ["전체 인구", "65세 이상 인구"],
                f"🔵 {region_A}": [df_A["전체인구"], df_A["고령인구"]],
                f"🔴 {region_B}": [df_B["전체인구"], df_B["고령인구"]]
            })

            fig_comp_bar = px.bar(
                comp_pop_df,
                x="구분",
                y=[f"🔵 {region_A}", f"🔴 {region_B}"],
                barmode="group",
                color_discrete_sequence=["#2563eb", "#ef4444"]
            )
            fig_comp_bar.update_layout(
                yaxis=dict(title="인원수 (명)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin={"r":10, "t":10, "l":10, "b":10},
                height=380
            )
            st.plotly_chart(fig_comp_bar, use_container_width=True)

# ------------------------------------------
# TAB 3: 버블 산점도 분석
# ------------------------------------------
with tab_scatter:
    st.markdown("##### 🎯 65세 이상 절대 인구수 vs 고령화 비율 (4분면 매트릭스)")
    st.caption("비율만 높은 군 단위 지자체와, 비율은 낮아도 실제 노인 수가 많은 대도시 지자체의 특성을 한눈에 비교합니다.")

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
    fig_bubble.update_layout(height=580, margin={"r":10, "t":30, "l":10, "b":10})
    st.plotly_chart(fig_bubble, use_container_width=True)

# ------------------------------------------
# TAB 4: 시도 트리맵
# ------------------------------------------
with tab_tree:
    st.markdown("##### 🔲 시·도별 시군구 계층 구조 트리맵")
    st.caption("네모 박스를 클릭하면 원하는 시·도 내 시군구 구조로 드릴다운(Zoom-in) 탐색이 가능합니다.")

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

# ==========================================
# 6. 하단 데이터 정리
# ==========================================
st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown(f"##### 📋 {selected_year}년 고령화율 극단 지자체 (Top 10 / Bottom 10)")

col1, col2 = st.columns(2)

top10 = df_year.sort_values(by="고령화율", ascending=False).head(10)[["지역명", "고령화율"]].reset_index(drop=True)
top10.index = top10.index + 1
top10.columns = ["지역명", "고령화율 (%)"]

bottom10 = df_year.sort_values(by="고령화율", ascending=True).head(10)[["지역명", "고령화율"]].reset_index(drop=True)
bottom10.index = bottom10.index + 1
bottom10.columns = ["지역명", "고령화율 (%)"]

with col1:
    st.markdown("🔴 **고령화율 가장 높은 지역 Top 10**")
    st.dataframe(top10, use_container_width=True)

with col2:
    st.markdown("🔵 **고령화율 가장 낮은 지역 Top 10**")
    st.dataframe(bottom10, use_container_width=True)
