import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests

# ==========================================
# 1. 스트림릿 페이지 설정
# ==========================================
st.set_page_config(
    page_title="전국 고령화 대시보드",
    page_icon="👵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 대시보드 제목 및 설명
st.title("📊 대한민국 시군구 고령화율 대시보드")
st.markdown("2015년~2026년 전국 시군구별 65세 이상 인구 비율(고령화율) 변화와 지역별 상세 분석을 제공합니다.")

# ==========================================
# 2. 데이터 불러오기 및 전처리 (캐싱 활용)
# ==========================================
@st.cache_data
def load_all_data():
    """인구 CSV 데이터를 읽어와 연도별·시군구별 고령화율을 계산합니다."""
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # 행정동 코드가 숫자로 바뀌어 앞자리 0이 손실되는 것을 막기 위해 string으로 로드
    df = pd.read_csv(pop_url, dtype={"코드": str})
    
    # 10자리 행정동 코드에서 앞 5자리를 잘라 시군구 코드로 지정
    df["sigungu_code"] = df["코드"].str[:5]
    
    # 나이 관련 열 찾기 ('계_'로 시작하는 열들)
    total_cols = [c for c in df.columns if c.startswith("계_")]
    
    # 65세 이상 나이 열 필터링 ('계_65세' ~ '계_100세 이상')
    elderly_cols = []
    for col in total_cols:
        age_str = col.replace("계_", "").replace("세", "").replace(" 이상", "")
        if age_str.isdigit() and int(age_str) >= 65:
            elderly_cols.append(col)
        elif age_str == "100":
            elderly_cols.append(col)
            
    # 행 단위 총인구 및 고령인구 합산
    df["전체인구"] = df[total_cols].sum(axis=1)
    df["고령인구"] = df[elderly_cols].sum(axis=1)
    
    # 연도 및 시군구 단위로 집계
    sigungu_yearly = df.groupby(["연도", "sigungu_code"]).agg({
        "시도": "first",
        "시군구": "first",
        "전체인구": "sum",
        "고령인구": "sum"
    }).reset_index()
    
    # 고령화율(%) 계산 및 소수점 첫째자리 정리
    sigungu_yearly["고령화율"] = (sigungu_yearly["고령인구"] / sigungu_yearly["전체인구"]) * 100
    sigungu_yearly["고령화율"] = sigungu_yearly["고령화율"].round(1)
    
    # 결측치 처리 후 검색용 시도+시군구 전체 이름 열 생성 (예: "서울특별시 종로구")
    sigungu_yearly["시도"] = sigungu_yearly["시도"].fillna("")
    sigungu_yearly["시군구"] = sigungu_yearly["시군구"].fillna("")
    sigungu_yearly["지역명"] = (sigungu_yearly["시도"] + " " + sigungu_yearly["시군구"]).str.strip()
    
    # 5단계 범주형 구간 만들기 (19%, 23%, 28%, 38% 기준)
    bins = [0, 19, 23, 28, 38, 100]
    labels = ["19% 미만", "19% 이상 ~ 23% 미만", "23% 이상 ~ 28% 미만", "28% 이상 ~ 38% 미만", "38% 이상"]
    sigungu_yearly["고령화 구간"] = pd.cut(sigungu_yearly["고령화율"], bins=bins, labels=labels, right=False)
    
    return sigungu_yearly

@st.cache_data
def load_geojson():
    """시군구 GeoJSON 경계 데이터를 불러옵니다."""
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    res = requests.get(geojson_url)
    return res.json()

# 데이터 로딩
sigungu_yearly = load_all_data()
geojson_data = load_geojson()

# 연도 범위 파악
min_year = int(sigungu_yearly["연도"].min())
max_year = int(sigungu_yearly["연도"].max())

# ==========================================
# 3. 사이드바 필터 (연도 슬라이더 & 지역 검색)
# ==========================================
st.sidebar.header("⚙️ 대시보드 설정")

# 연도 선택 타임슬라이더
selected_year = st.sidebar.slider(
    "📅 분석 연도 선택",
    min_value=min_year,
    max_value=max_year,
    value=max_year,
    step=1
)

# 지역 선택 드롭다운 (결측치 및 공백 제거 후 정렬)
valid_regions = [r for r in sigungu_yearly["지역명"].dropna().unique() if r]
all_regions = ["전국 (전체)"] + sorted(valid_regions)

selected_region = st.sidebar.selectbox(
    "🔍 상세 분석할 지역 선택",
    options=all_regions,
    index=0
)

# 선택된 연도 데이터 필터링
df_year = sigungu_yearly[sigungu_yearly["연도"] == selected_year].copy()

# ==========================================
# 4. 상단 KPI 요약 카드 (4개)
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
    st.metric(
        label=f"🌐 전국 평균 고령화율 ({selected_year}년)",
        value=f"{nat_aging_rate}%",
        delta=f"전체인구 {nat_total_pop:,}명"
    )

with kpi2:
    st.metric(
        label="🚨 초고령 지자체 (20% 이상)",
        value=f"{super_aged_count}개 시군구",
        delta=f"전국 지자체의 {super_aged_ratio}%"
    )

with kpi3:
    st.metric(
        label="🔴 최고 고령화 지역",
        value=f"{top_region_row['지역명']}",
        delta=f"{top_region_row['고령화율']}%"
    )

with kpi4:
    st.metric(
        label="🔵 최저 고령화 지역",
        value=f"{bottom_region_row['지역명']}",
        delta=f"{bottom_region_row['고령화율']}%"
    )

st.markdown("---")

# ==========================================
# 5. 메인 화면: 지도 & 추이 그래프 (2개 컬럼)
# ==========================================
col_map, col_chart = st.columns([1.2, 0.8])

# ------------------------------------------
# (좌) 전국 지도 시각화
# ------------------------------------------
with col_map:
    st.subheader(f"🗺️ 전국 시군구 고령화 지도 ({selected_year}년)")
    
    color_map = {
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
        color_discrete_map=color_map,
        category_orders={"고령화 구간": ["19% 미만", "19% 이상 ~ 23% 미만", "23% 이상 ~ 28% 미만", "28% 이상 ~ 38% 미만", "38% 이상"]},
        hover_name="지역명",
        hover_data={
            "시도": True,
            "시군구": True,
            "고령화율": ":.1f%",
            "전체인구": ":,명",
            "고령인구": ":,명",
            "sigungu_code": False,
            "고령화 구간": False
        },
        center={"lat": 35.8, "lon": 127.8},
        zoom=6.1,
        mapbox_style="white-bg"
    )

    fig_map.update_layout(
        margin={"r":0, "t":10, "l":0, "b":0},
        legend_title_text="고령화율 구간",
        height=520
    )

    st.plotly_chart(fig_map, use_container_width=True)

# ------------------------------------------
# (우) 상세 지역 10년 추이 시각화
# ------------------------------------------
with col_chart:
    st.subheader("📈 연도별 고령화율 변화 추이")
    
    nat_trend = sigungu_yearly.groupby("연도").apply(
        lambda x: (x["고령인구"].sum() / x["전체인구"].sum()) * 100
    ).reset_index(name="전국평균")
    nat_trend["전국평균"] = nat_trend["전국평균"].round(1)

    fig_line = go.Figure()

    fig_line.add_trace(go.Scatter(
        x=nat_trend["연도"],
        y=nat_trend["전국평균"],
        mode="lines+markers",
        name="전국 평균",
        line=dict(color="#94a3b8", width=2, dash="dash")
    ))

    if selected_region != "전국 (전체)":
        reg_df = sigungu_yearly[sigungu_yearly["지역명"] == selected_region].sort_values("연도")
        
        df_year_sorted = df_year.sort_values(by="고령화율", ascending=False).reset_index(drop=True)
        rank_matches = df_year_sorted[df_year_sorted["지역명"] == selected_region].index
        
        if len(rank_matches) > 0 and len(reg_df[reg_df["연도"] == selected_year]) > 0:
            rank = rank_matches[0] + 1
            curr_rate = reg_df[reg_df["연도"] == selected_year]["고령화율"].values[0]
            st.info(f"📍 **{selected_region}** ({selected_year}년 기준)\n- **고령화율:** `{curr_rate}%`\n- **전국 순위:** `255개 지자체 중 {rank}위`")

        fig_line.add_trace(go.Scatter(
            x=reg_df["연도"],
            y=reg_df["고령화율"],
            mode="lines+markers",
            name=selected_region,
            line=dict(color="#2563eb", width=3)
        ))
    else:
        st.info("👈 사이드바에서 특정 **시군구**를 선택하시면 해당 지역의 10년 추이를 비교할 수 있습니다.")

    fig_line.update_layout(
        xaxis=dict(title="연도", dtick=1),
        yaxis=dict(title="고령화율 (%)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin={"r":10, "t":10, "l":10, "b":10},
        height=420
    )

    st.plotly_chart(fig_line, use_container_width=True)

st.markdown("---")

# ==========================================
# 6. 하단 데이터 표 (상위/하위 10개 & 속도 Top 10)
# ==========================================
st.subheader(f"📋 {selected_year}년 주요 지표별 시군구 순위")

tab1, tab2, tab3 = st.tabs(["🔴 고령화율 Top 10", "🔵 고령화율 Bottom 10", "⚡ 고령화 속도(증가폭) Top 10"])

with tab1:
    top10 = df_year.sort_values(by="고령화율", ascending=False).head(10)
    top10_view = top10[["시도", "시군구", "고령화율", "전체인구", "고령인구"]].reset_index(drop=True)
    st.dataframe(top10_view, use_container_width=True)

with tab2:
    bottom10 = df_year.sort_values(by="고령화율", ascending=True).head(10)
    bottom10_view = bottom10[["시도", "시군구", "고령화율", "전체인구", "고령인구"]].reset_index(drop=True)
    st.dataframe(bottom10_view, use_container_width=True)

with tab3:
    start_df = sigungu_yearly[sigungu_yearly["연도"] == min_year].set_index("sigungu_code")["고령화율"]
    curr_df = df_year.set_index("sigungu_code")
    
    curr_df["시작_고령화율"] = start_df
    curr_df["증가폭(%p)"] = (curr_df["고령화율"] - curr_df["시작_고령화율"]).round(1)
    
    fastest10 = curr_df.sort_values(by="증가폭(%p)", ascending=False).head(10)
    fastest10_view = fastest10[["시도", "시군구", "시작_고령화율", "고령화율", "증가폭(%p)"]].reset_index(drop=True)
    fastest10_view.columns = ["시도", "시군구", f"{min_year}년 고령화율", f"{selected_year}년 고령화율", f"증가폭(%p, {min_year}~{selected_year})"]
    
    st.markdown(f"**{min_year}년 대비 {selected_year}년까지 고령화율이 가장 크게 상승한 지자체 10곳**입니다.")
    st.dataframe(fastest10_view, use_container_width=True)
