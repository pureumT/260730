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
    page_title="전국 고령화 & 미래 예측 대시보드",
    layout="wide"
)

st.title("📊 전국 시군구 고령화율 & 미래 예측 대시보드")
st.markdown("2015~2026년 고령화 현황과 함께 **지역별 미래 고령화율 및 중·고교 입학생 수** 예측을 제공합니다.")

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
            
    # 전체 인구, 고령 인구 및 중/고교 입학 연령 인구 합산
    df["전체인구"] = df[total_cols].sum(axis=1)
    df["고령인구"] = df[elderly_cols].sum(axis=1)
    
    # 중학 입학(만 12세) / 고교 입학(만 15세) 열 존재 여부 확인 후 가져오기
    df["중학입학인구"] = df["계_12세"] if "계_12세" in df.columns else 0
    df["고교입학인구"] = df["계_15세"] if "계_15세" in df.columns else 0

    # 연도 및 시군구 단위로 집계
    sigungu_df = df.groupby(["연도", "sigungu_code"]).agg({
        "시도": "first",
        "시군구": "first",
        "전체인구": "sum",
        "고령인구": "sum",
        "중학입학인구": "sum",
        "고교입학인구": "sum"
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
    
    # 미래 학령인구 추정을 위해 최신 연도(2026년)의 0~15세 연령별 인구 보존
    latest_year = df["연도"].max()
    df_latest_age = df[df["연도"] == latest_year].copy()
    
    return sigungu_df, df_latest_age, latest_year

@st.cache_data
def load_geojson():
    """시군구 GeoJSON 경계 데이터를 불러옵니다."""
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(geojson_url)
    return response.json()

# 데이터 로딩
sigungu_yearly, df_latest_age, max_year = load_population_data()
geojson_data = load_geojson()

min_year = int(sigungu_yearly["연도"].min())

# ==========================================
# 3. 사이드바 설정 (연도 선택 및 상세 지역 선택)
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
    "🔍 미래 예측 및 상세 분석할 시군구 선택",
    options=all_regions,
    index=0
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
# 5. 메인 레이아웃: 지도 & 예측/추이 그래프
# ==========================================
col_map, col_chart = st.columns([1.1, 0.9])

# ------------------------------------------
# (좌) 지도 시각화
# ------------------------------------------
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
    fig_map.update_layout(margin={"r":0, "t":10, "l":0, "b":0}, height=550)
    st.plotly_chart(fig_map, use_container_width=True)

# ------------------------------------------
# (우) 고령화율 트렌드 및 미래 예측 (2035년까지)
# ------------------------------------------
with col_chart:
    st.subheader("🔮 고령화율 과거 추이 및 2035년 미래 예측")

    if selected_region != "전국 (전체)":
        reg_df = sigungu_yearly[sigungu_yearly["지역명"] == selected_region].sort_values("연도")
        
        # 선형 회귀 분석을 통한 2035년까지의 미래 고령화율 예측
        X = reg_df["연도"].values
        y = reg_df["고령화율"].values
        poly = np.polyfit(X, y, 1)  # 1차 선형 방정식
        
        future_years = np.arange(max_year + 1, 2036)
        future_y = np.polyval(poly, future_years).round(1)

        fig_pred = go.Figure()

        # 관측 데이터 (2015~2026)
        fig_pred.add_trace(go.Scatter(
            x=X, y=y,
            mode="lines+markers",
            name="실제 관측치",
            line=dict(color="#2563eb", width=3)
        ))

        # 예측 데이터 (2027~2035)
        fig_pred.add_trace(go.Scatter(
            x=np.append(X[-1], future_years),
            y=np.append(y[-1], future_y),
            mode="lines+markers",
            name="미래 예측치",
            line=dict(color="#ef4444", width=3, dash="dot")
        ))

        # 2035년 예상 값 표시
        pred_2035 = future_y[-1]
        st.info(f"📍 **{selected_region}**\n- **{max_year}년 현재:** `{y[-1]}%`\n- **2035년 예상 고령화율:** `{pred_2035}%` (현재 대비 `+{round(pred_2035 - y[-1], 1)}%p` 상승 추세)")

        fig_pred.update_layout(
            xaxis=dict(title="연도", dtick=2),
            yaxis=dict(title="고령화율 (%)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin={"r":10, "t":10, "l":10, "b":10},
            height=430
        )
        st.plotly_chart(fig_pred, use_container_width=True)
    else:
        st.warning("👈 **사이드바에서 특정 시군구를 선택**하시면 2035년까지의 미래 고령화율 예측을 보실 수 있습니다.")

st.markdown("---")

# ==========================================
# 6. 지역 선택 시: 중·고교 입학생 인원 예측 (코호트 분석)
# ==========================================
if selected_region != "전국 (전체)":
    st.subheader(f"🎓 {selected_region} - 미래 중·고등학교 입학생 수 예측")
    
    # 선택된 지역의 최신 0~15세 연령별 인구 가져오기
    df_reg_age = df_latest_age.copy()
    df_reg_age["시도"] = df_reg_age["시도"].fillna("")
    df_reg_age["시군구"] = df_reg_age["시군구"].fillna("")
    df_reg_age["지역명"] = (df_reg_age["시도"] + " " + df_reg_age["시군구"]).str.strip()
    
    reg_latest = df_reg_age[df_reg_age["지역명"] == selected_region]

    # 현재 0~12세 인구를 기반으로 미래 연도별 중1(만 12세) / 고1(만 15세) 입학생 수 예측
    years_ahead = []
    mid_school_pred = []
    high_school_pred = []

    # 최근 3개년 과거 실제 입학생 수
    past_years = [max_year - 2, max_year - 1, max_year]
    past_df = sigungu_yearly[(sigungu_yearly["지역명"] == selected_region) & (sigungu_yearly["연도"].isin(past_years))]
    
    # 미래 예측 (최신 연도 2026년 인구 코호트 활용)
    if len(reg_latest) > 0:
        row = reg_latest.iloc[0]
        
        # 미래 6년 간 예측
        for i in range(1, 7):
            f_year = max_year + i
            years_ahead.append(f_year)
            
            # 만 12세 중학 입학: 현재 (12 - i)세의 인구
            target_mid_age = 12 - i
            mid_col = f"계_{target_mid_age}세"
            mid_val = row[mid_col] if (target_mid_age >= 0 and mid_col in row) else 0
            mid_school_pred.append(mid_val)
            
            # 만 15세 고교 입학: 현재 (15 - i)세의 인구
            target_high_age = 15 - i
            high_col = f"계_{target_high_age}세"
            high_val = row[high_col] if (target_high_age >= 0 and high_col in row) else 0
            high_school_pred.append(high_val)

        # 차트 생성을 위한 데이터프레임 결합
        df_students = pd.DataFrame({
            "연도": [str(y) for y in years_ahead],
            "중학교 입학 예정자 (만 12세)": mid_school_pred,
            "고등학교 입학 예정자 (만 15세)": high_school_pred
        })

        col_sch1, col_sch2 = st.columns([1, 1])

        with col_sch1:
            fig_sch = px.bar(
                df_students,
                x="연도",
                y=["중학교 입학 예정자 (만 12세)", "고등학교 입학 예정자 (만 15세)"],
                barmode="group",
                title="향후 6년간 입학 예정자 수 추이 (명)",
                color_discrete_sequence=["#3b82f6", "#f59e0b"]
            )
            fig_sch.update_layout(xaxis_title="연도", yaxis_title="인원수 (명)", legend_title_text="구분")
            st.plotly_chart(fig_sch, use_container_width=True)

        with col_sch2:
            st.markdown("#### 📌 학령인구 분석 요약")
            curr_mid = mid_school_pred[0]
            future_mid = mid_school_pred[-1]
            diff_mid = future_mid - curr_mid
            
            st.write(f"- **{years_ahead[0]}년 예상 중1 입학생:** `{curr_mid:,}명`")
            st.write(f"- **{years_ahead[-1]}년 예상 중1 입학생:** `{future_mid:,}명` (`{diff_mid:+,}명` 변화)")
            
            if diff_mid < 0:
                st.warning("⚠️ **학령인구 감소 경고**: 유소년 인구 감소로 인해 향후 관내 중·고등학교 학급 감축 및 폐교 가능성이 높습니다.")
            else:
                st.success("✅ **학령인구 유지/증가**: 관내 입학 예정자 인원이 일정 수준 이상 유지되고 있습니다.")

            st.caption("※ 본 예측은 전출입 이동이 없다는 가정하에 현재 연령별 인구수(코호트)를 추적한 결과입니다.")

# ==========================================
# 7. 하단 데이터 표 (상위 10개 & 하위 10개)
# ==========================================
st.markdown("---")
st.subheader(f"📋 {selected_year}년 고령화율 상위 & 하위 10개 지역")

col1, col2 = st.columns(2)

top10 = df_year.sort_values(by="고령화율", ascending=False).head(10)
top10_display = top10[["시도", "시군구", "고령화율", "전체인구", "고령인구"]].reset_index(drop=True)

bottom10 = df_year.sort_values(by="고령화율", ascending=True).head(10)
bottom10_display = bottom10[["시도", "시군구", "고령화율", "전체인구", "고령인구"]].reset_index(drop=True)

with col1:
    st.markdown("🔴 **고령화율 가장 높은 10곳**")
    st.dataframe(top10_display, use_container_width=True)

with col2:
    st.markdown("🔵 **고령화율 가장 낮은 10곳**")
    st.dataframe(bottom10_display, use_container_width=True)
