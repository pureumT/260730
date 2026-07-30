import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(
    page_title="전국 고령화 시계열 빅데이터 분석 대시보드",
    layout="wide"
)

st.title("📊 전국 시군구 고령화 시계열 빅데이터 대시보드")
st.markdown("2015년~2026년 10년 이상의 인구 빅데이터를 기반으로 **고령화 타임랩스, 진입 D-Day, 미래 학령인구 예측**을 제공합니다.")

# ==========================================
# 2. 데이터 불러오기 및 전처리
# ==========================================
@st.cache_data
def load_population_data():
    """인구 데이터를 불러오고 연도별·시군구별 고령화율 및 연령별 인구를 계산합니다."""
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # 코드는 5자리 시군구 추출을 위해 문자열(dtype=str)로 로드
    df = pd.read_csv(pop_url, dtype={"코드": str})
    
    # 행정동 코드(10자리)의 앞 5자리를 잘라서 시군구 코드로 생성
    df["sigungu_code"] = df["코드"].str[:5]
    
    # 전체 인구 및 65세 이상 인구 열 추출
    total_cols = [c for c in df.columns if c.startswith("계_")]
    elderly_cols = []
    for col in total_cols:
        age_str = col.replace("계_", "").replace("세", "").replace(" 이상", "")
        if age_str.isdigit() and int(age_str) >= 65:
            elderly_cols.append(col)
        elif age_str == "100":
            elderly_cols.append(col)
            
    # 전체 인구 및 고령 인구 합산
    df["전체인구"] = df[total_cols].sum(axis=1)
    df["고령인구"] = df[elderly_cols].sum(axis=1)
    
    # 연도 및 시군구 단위로 집계
    sigungu_df = df.groupby(["연도", "sigungu_code"]).agg({
        "시도": "first",
        "시군구": "first",
        "전체인구": "sum",
        "고령인구": "sum"
    }).reset_index()
    
    # 고령화율(%) 계산
    sigungu_df["고령화율"] = (sigungu_df["고령인구"] / sigungu_df["전체인구"]) * 100
    sigungu_df["고령화율"] = sigungu_df["고령화율"].round(1)
    
    # 시도 및 시군구 결측치 처리 후 전체 지역명 생성
    sigungu_df["시도"] = sigungu_df["시도"].fillna("")
    sigungu_df["시군구"] = sigungu_df["시군구"].fillna("")
    sigungu_df["지역명"] = (sigungu_df["시도"] + " " + sigungu_df["시군구"]).str.strip()
    
    # 5단계 범주형 구간 나누기
    bins = [0, 19, 23, 28, 38, 100]
    labels = ["19% 미만", "19% 이상 ~ 23% 미만", "23% 이상 ~ 28% 미만", "28% 이상 ~ 38% 미만", "38% 이상"]
    sigungu_df["고령화 구간"] = pd.cut(sigungu_df["고령화율"], bins=bins, labels=labels, right=False)
    
    # 연도별 전국 순위 계산 (1위: 고령화율이 가장 높은 지역)
    sigungu_df["전국순위"] = sigungu_df.groupby("연도")["고령화율"].rank(ascending=False, method="min").astype(int)
    
    # 미래 학령인구 추정을 위해 최신 연도 인구 보존
    latest_year = df["연도"].max()
    df_latest_age = df[df["연도"] == latest_year].copy()
    
    return sigungu_df, df_latest_age, latest_year

@st.cache_data
def load_geojson():
    """시군구 GeoJSON 경계 데이터 및 중심 좌표(핀 표기용)를 계산해 불러옵니다."""
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(geojson_url)
    geojson = response.json()
    
    # 각 시군구의 중심점 좌표 계산 (핀 표시 목적)
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

# 데이터 로딩
sigungu_yearly, df_latest_age, max_year = load_population_data()
geojson_data, geo_centers = load_geojson()

min_year = int(sigungu_yearly["연도"].min())

# ==========================================
# 3. 사이드바 설정 (연도 선택 및 빠른 지역 검색)
# ==========================================
st.sidebar.subheader("📌 데이터 설정")

selected_year = st.sidebar.slider(
    "📅 지도 표시 연도 선택",
    min_value=min_year,
    max_value=max_year,
    value=max_year,
    step=1
)

valid_regions = [r for r in sigungu_yearly["지역명"].dropna().unique() if r]
all_regions = ["전국 (전체)"] + sorted(valid_regions)

selected_region = st.sidebar.selectbox(
    "🔍 지역 검색 및 선택 (상세 분석)",
    options=all_regions,
    index=0,
    help="지역 이름을 입력하여 빠르게 검색할 수 있습니다."
)

df_year = sigungu_yearly[sigungu_yearly["연도"] == selected_year].copy()

# ==========================================
# 4. 상단 KPI 요약 정보 카드
# ==========================================
nat_total_pop = df_year["전체인구"].sum()
nat_elderly_pop = df_year["고령인구"].sum()
nat_aging_rate = round((nat_elderly_pop / nat_total_pop) * 100, 1)

super_aged_count = len(df_year[df_year["고령화율"] >= 20.0])
super_aged_ratio = round((super_aged_count / len(df_year)) * 100, 1)

top_region_row = df_year.sort_values(by="고령화율", ascending=False).iloc[0]
bottom_region_row = df_year.sort_values(by="고령화율", ascending=True).iloc[0]

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric(f"🌐 전국 평균 고령화율 ({selected_year}년)", f"{nat_aging_rate}%", f"전체 {nat_total_pop:,}명")
with kpi2:
    st.metric("🚨 초고령 지자체 (20% 이상)", f"{super_aged_count}개 시군구", f"전국의 {super_aged_ratio}%")
with kpi3:
    st.metric("🔴 최고 고령화 지역", f"{top_region_row['지역명']}", f"{top_region_row['고령화율']}%")
with kpi4:
    st.metric("🔵 최저 고령화 지역", f"{bottom_region_row['지역명']}", f"{bottom_region_row['고령화율']}%")

st.markdown("---")

# ==========================================
# 5. 탭 구성 (시계열 빅데이터 다각도 분석)
# ==========================================
tab_main, tab_timelapse, tab_dday, tab_rank = st.tabs([
    "🗺️ 지도 & 미래 예측", 
    "🎞️ 10년 고령화 타임랩스", 
    "🚨 초고령사회 진입 D-Day", 
    "🏎️ 순위 변동 & 가속도"
])

# ------------------------------------------
# TAB 1: 지도 및 미래 예측 (기존 핵심 화면)
# ------------------------------------------
with tab_main:
    col_map, col_chart = st.columns([1.1, 0.9])

    with col_map:
        st.subheader(f"🗺️ 전국 시군구 고령화 지도 ({selected_year}년)")

        color_discrete_map = {
            "19% 미만": "#edf8fb",
            "19% 이상 ~ 23% 미만": "#b2e2e2",
            "23% 이상 ~ 28% 미만": "#66c2a4",
            "28% 이상 ~ 38% 미만": "#2ca25f",
            "38% 이상": "#006d2c"
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

        # 선택한 시군구 핀 마커 표시
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
                        marker=dict(size=14, color="red"),
                        text=[f"📍 {selected_region}"],
                        textposition="top center",
                        name="선택된 지역"
                    ))
                    fig_map.update_layout(mapbox=dict(center=dict(lat=lat, lon=lon), zoom=8.0))

        fig_map.update_layout(margin={"r":0, "t":10, "l":0, "b":0}, height=520)
        st.plotly_chart(fig_map, use_container_width=True)

    with col_chart:
        st.subheader("🔮 고령화율 과거 추이 및 2035년 미래 예측")

        if selected_region != "전국 (전체)":
            reg_df = sigungu_yearly[sigungu_yearly["지역명"] == selected_region].sort_values("연도")
            
            X = reg_df["연도"].values
            y = reg_df["고령화율"].values
            poly = np.polyfit(X, y, 1)
            
            future_years = np.arange(max_year + 1, 2036)
            future_y = np.polyval(poly, future_years).round(1)

            fig_pred = go.Figure()
            fig_pred.add_trace(go.Scatter(x=X, y=y, mode="lines+markers", name="실제 관측치", line=dict(color="#2563eb", width=3)))
            fig_pred.add_trace(go.Scatter(x=np.append(X[-1], future_years), y=np.append(y[-1], future_y), mode="lines+markers", name="미래 예측치", line=dict(color="#ef4444", width=3, dash="dot")))

            pred_2035 = future_y[-1]
            st.info(f"📍 **{selected_region}**\n- **{max_year}년 현재:** `{y[-1]}%`\n- **2035년 예상 고령화율:** `{pred_2035}%` (현재 대비 `+{round(pred_2035 - y[-1], 1)}%p` 상승 추세)")

            fig_pred.update_layout(
                xaxis=dict(title="연도", dtick=2),
                yaxis=dict(title="고령화율 (%)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin={"r":10, "t":10, "l":10, "b":10},
                height=400
            )
            st.plotly_chart(fig_pred, use_container_width=True)
        else:
            st.warning("👈 **사이드바에서 검색창을 이용해 특정 시군구를 선택**하시면 핀 표시와 함께 2035년까지의 미래 예측을 보실 수 있습니다.")

    # 학령인구 예측
    if selected_region != "전국 (전체)":
        st.markdown("---")
        st.subheader(f"🎓 {selected_region} - 미래 중·고등학교 입학생 수 예측")
        
        df_reg_age = df_latest_age.copy()
        df_reg_age["시도"] = df_reg_age["시도"].fillna("")
        df_reg_age["시군구"] = df_reg_age["시군구"].fillna("")
        df_reg_age["지역명"] = (df_reg_age["시도"] + " " + df_reg_age["시군구"]).str.strip()
        
        reg_latest = df_reg_age[df_reg_age["지역명"] == selected_region]

        years_ahead = []
        mid_school_pred = []
        high_school_pred = []

        if len(reg_latest) > 0:
            row = reg_latest.iloc[0]
            for i in range(1, 7):
                f_year = max_year + i
                years_ahead.append(f_year)
                target_mid_age = 12 - i
                mid_col = f"계_{target_mid_age}세"
                mid_val = row[mid_col] if (target_mid_age >= 0 and mid_col in row) else 0
                mid_school_pred.append(mid_val)
                
                target_high_age = 15 - i
                high_col = f"계_{target_high_age}세"
                high_val = row[high_col] if (target_high_age >= 0 and high_col in row) else 0
                high_school_pred.append(high_val)

            df_students = pd.DataFrame({
                "연도": [str(y) for y in years_ahead],
                "중학교 입학 예정자 (만 12세)": mid_school_pred,
                "고등학교 입학 예정자 (만 15세)": high_school_pred
            })

            col_sch1, col_sch2 = st.columns([1, 1])
            with col_sch1:
                fig_sch = px.bar(
                    df_students, x="연도", y=["중학교 입학 예정자 (만 12세)", "고등학교 입학 예정자 (만 15세)"],
                    barmode="group", title="향후 6년간 입학 예정자 수 추이 (명)", color_discrete_sequence=["#3b82f6", "#f59e0b"]
                )
                st.plotly_chart(fig_sch, use_container_width=True)

            with col_sch2:
                st.markdown("#### 📌 학령인구 분석 요약")
                curr_mid = mid_school_pred[0]
                future_mid = mid_school_pred[-1]
                diff_mid = future_mid - curr_mid
                st.write(f"- **{years_ahead[0]}년 예상 중1 입학생:** `{curr_mid:,}명`")
                st.write(f"- **{years_ahead[-1]}년 예상 중1 입학생:** `{future_mid:,}명` (`{diff_mid:+,}명` 변화)")
                if diff_mid < 0:
                    st.warning("⚠️ **학령인구 감소 경고**: 유소년 인구 감소로 인해 관내 학교 감축 가능성이 높습니다.")
                else:
                    st.success("✅ **학령인구 유지**: 관내 입학 예정자 인원이 일정 수준 이상 유지되고 있습니다.")

# ------------------------------------------
# TAB 2: 10년 고령화 타임랩스 애니메이션
# ------------------------------------------
with tab_timelapse:
    st.subheader("🎞️ 2015~2026 대한민국 고령화 타임랩스")
    st.markdown("하단의 **[▶ 재생] 버튼**을 누르면 시간의 흐름에 따라 전국 지자체가 붉게 변화하는 고령화 진행 과정을 보실 수 있습니다.")

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
    fig_anim.update_layout(margin={"r":0, "t":10, "l":0, "b":0}, height=600)
    st.plotly_chart(fig_anim, use_container_width=True)

# ------------------------------------------
# TAB 3: 초고령사회(20%) 진입 D-Day 분석
# ------------------------------------------
with tab_dday:
    st.subheader("🚨 초고령사회 (고령화율 20% 이상) 진입 연도 및 D-Day 분석")
    st.markdown("UN 기준 고령화율 20% 이상을 **초고령사회**로 정의합니다. 각 지자체의 진입 완료 연도 및 향후 진입 예상 시점을 산출합니다.")

    # 각 지자체별 초고령사회 진입 연도 계산
    dday_list = []
    for reg, grp in sigungu_yearly.groupby("지역명"):
        grp = grp.sort_values("연도")
        super_aged = grp[grp["고령화율"] >= 20.0]
        
        if len(super_aged) > 0:
            first_entry_year = int(super_aged.iloc[0]["연도"])
            status = f"✅ {first_entry_year}년 진입 완료"
            d_day = first_entry_year - max_year
        else:
            # 미래 진입 연도 선형 예측
            X = grp["연도"].values
            y = grp["고령화율"].values
            poly = np.polyfit(X, y, 1)
            # y = ax + b -> x = (20 - b) / a
            if poly[0] > 0:
                est_year = int((20.0 - poly[1]) / poly[0])
                status = f"⏳ {est_year}년 진입 예상"
                d_day = est_year - max_year
            else:
                status = "🟢 유지 예상"
                d_day = 999
                
        # 최근 존재하는 연도의 고령화율 안전 추출 (IndexError 방지)
        curr_rate_series = grp[grp["연도"] == max_year]["고령화율"]
        if not curr_rate_series.empty:
            curr_rate = curr_rate_series.values[0]
        else:
            curr_rate = grp.iloc[-1]["고령화율"]

        dday_list.append({
            "지역명": reg,
            f"{max_year}년 고령화율": f"{curr_rate}%",
            "초고령사회 상태": status,
            "D-Day (연)": d_day if d_day != 999 else "-"
        })

    df_dday = pd.DataFrame(dday_list)

    col_d1, col_d2 = st.columns([1, 1])
    with col_d1:
        st.markdown("##### 🚨 이미 초고령사회에 진입한 지자체")
        st.dataframe(df_dday[df_dday["초고령사회 상태"].str.contains("진입 완료")].reset_index(drop=True), use_container_width=True)

    with col_d2:
        st.markdown("##### ⏳ 앞으로 초고령사회 진입 임박 지자체 (진입 예정)")
        st.dataframe(df_dday[df_dday["초고령사회 상태"].str.contains("진입 예상")].sort_values("D-Day (연)").reset_index(drop=True), use_container_width=True)

# ------------------------------------------
# TAB 4: 순위 변동 & 고령화 가속도
# ------------------------------------------
with tab_rank:
    st.subheader("🏎️ 지난 10년 고령화 순위 변동 & 가속도 Top 10")
    
    # 2015년 대비 2026년 순위 변동 및 상승폭 계산
    df_min = sigungu_yearly[sigungu_yearly["연도"] == min_year].set_index("지역명")
    df_max = sigungu_yearly[sigungu_yearly["연도"] == max_year].set_index("지역명")

    # 두 데이터 프레임 간 지역명 인덱스를 안전하게 교집합 처리
    common_regions = df_min.index.intersection(df_max.index)

    rank_diff = pd.DataFrame({
        f"{min_year}년 고령화율": df_min.loc[common_regions, "고령화율"],
        f"{max_year}년 고령화율": df_max.loc[common_regions, "고령화율"],
        f"{min_year}년 순위": df_min.loc[common_regions, "전국순위"],
        f"{max_year}년 순위": df_max.loc[common_regions, "전국순위"],
        "순위 상승폭 (계단)": df_min.loc[common_regions, "전국순위"] - df_max.loc[common_regions, "전국순위"],
        "고령화율 증가폭 (%p)": (df_max.loc[common_regions, "고령화율"] - df_min.loc[common_regions, "고령화율"]).round(1)
    }).reset_index()

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown("##### 📈 10년간 전국 고령화 순위가 가장 급상승한 지자체")
        st.dataframe(rank_diff.sort_values(by="순위 상승폭 (계단)", ascending=False).head(10).reset_index(drop=True), use_container_width=True)

    with col_r2:
        st.markdown("##### ⚡ 10년간 고령화율 증가속도가 가장 빠른 지자체 (%p)")
        st.dataframe(rank_diff.sort_values(by="고령화율 증가폭 (%p)", ascending=False).head(10).reset_index(drop=True), use_container_width=True)

# ==========================================
# 6. 하단 간소화된 상위/하위 10개 지역 요약 표
# ==========================================
st.markdown("---")
st.subheader(f"📊 {selected_year}년 고령화율 상위 & 하위 10개 지역 (간단 요약)")

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
    st.markdown("🔴 **고령화율 가장 높은 지역 Top 10**")
    st.dataframe(top10_simple, use_container_width=True)

with col2:
    st.markdown("🔵 **고령화율 가장 낮은 지역 Top 10**")
    st.dataframe(bottom10_simple, use_container_width=True)
