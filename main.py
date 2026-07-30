import streamlit as st
import pandas as pd
import json
import requests

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="전국 시군구 고령화 지도",
    layout="wide"
)

st.title("📊 전국 시군구 고령화율 지도")
st.markdown("최신 연도 기준 전국 시군구별 65세 이상 인구 비율(고령화율)을 보여주는 지도입니다.")

# 2. 데이터 불러오기 (캐싱을 적용하여 속도 최적화)
@st.cache_data
def load_population_data():
    """인구 데이터를 불러오고 최신 연도의 시군구별 고령화율을 계산합니다."""
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # 코드는 5자리 시군구 추출을 위해 문자열(dtype=str)로 읽습니다.
    df = pd.read_csv(pop_url, dtype={"코드": str})
    
    # 가장 최신 연도 데이터만 추출
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()
    
    # 행정동 코드(10자리)의 앞 5자리를 잘라서 시군구 코드로 생성
    df_latest["sigungu_code"] = df_latest["코드"].str[:5]
    
    # 65세 이상 인구 열 찾기 ('계_65세' ~ '계_100세 이상')
    # 나이 열 목록에서 '계_'로 시작하고 65세 이상인 열들 지정
    total_cols = [c for c in df_latest.columns if c.startswith("계_")]
    # '계_0세' ~ '계_64세'를 제외한 65세 이상 열만 필터링
    elderly_cols = []
    for col in total_cols:
        age_str = col.replace("계_", "").replace("세", "").replace(" 이상", "")
        if age_str.isdigit() and int(age_str) >= 65:
            elderly_cols.append(col)
        elif age_str == "100": # '계_100세 이상' 처리
            elderly_cols.append(col)
            
    # 시군구 단위로 총 인구와 65세 이상 인구 합산
    # 시도, 시군구 명칭도 함께 집계 (첫번째 값 사용)
    df_latest["전체인구"] = df_latest[total_cols].sum(axis=1)
    df_latest["고령인구"] = df_latest[elderly_cols].sum(axis=1)
    
    sigungu_df = df_latest.groupby("sigungu_code").agg({
        "시도": "first",
        "시군구": "first",
        "전체인구": "sum",
        "고령인구": "sum"
    }).reset_index()
    
    # 고령화율(%) 계산 (65세 이상 인구 / 전체 인구 * 100)
    sigungu_df["고령화율"] = (sigungu_df["고령인구"] / sigungu_df["전체인구"]) * 100
    sigungu_df["고령화율"] = sigungu_df["고령화율"].round(1)
    
    # 5단계 구간 나누기 (19%, 23%, 28%, 38% 경계)
    # pd.cut을 이용해 범주형 라벨 부여
    bins = [0, 19, 23, 28, 38, 100]
    labels = ["19% 미만", "19% 이상 ~ 23% 미만", "23% 이상 ~ 28% 미만", "28% 이상 ~ 38% 미만", "38% 이상"]
    sigungu_df["고령화 구간"] = pd.cut(sigungu_df["고령화율"], bins=bins, labels=labels, right=False)
    
    return sigungu_df, latest_year

@st.cache_data
def load_geojson():
    """시군구 GeoJSON 경계 데이터를 불러옵니다."""
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(geojson_url)
    geojson = response.json()
    return geojson

# 데이터 로딩
sigungu_df, latest_year = load_population_data()
geojson_data = load_geojson()

st.sidebar.subheader("📌 데이터 정보")
st.sidebar.write(f"기준 연도: **{latest_year}년**")
st.sidebar.write(f"전국 시군구 수: **{len(sigungu_df)}개**")

# 3. Plotly 지도 시각화 (px.choropleth_mapbox 활용)
import plotly.express as px

# 5단계 색상 맵핑 (옅은 색 -> 진한 색)
color_discrete_map = {
    "19% 미만": "#edf8fb",
    "19% 이상 ~ 23% 미만": "#b2e2e2",
    "23% 이상 ~ 28% 미만": "#66c2a4",
    "28% 이상 ~ 38% 미만": "#2ca25f",
    "38% 이상": "#006d2c"
}

# 지도 생성
fig = px.choropleth_mapbox(
    sigungu_df,
    geojson=geojson_data,
    locations="sigungu_code",       # 데이터에서 지점 키가 될 열
    featureidkey="properties.코드", # GeoJSON에서 지점 키가 될 속성 경로
    color="고령화 구간",             # 범주형 구간에 따라 색상 매핑
    color_discrete_map=color_discrete_map,
    category_orders={"고령화 구간": ["19% 미만", "19% 이상 ~ 23% 미만", "23% 이상 ~ 28% 미만", "28% 이상 ~ 38% 미만", "38% 이상"]},
    hover_name="시군구",
    hover_data={
        "시도": True,
        "고령화율": ":.1f%",
        "sigungu_code": False,
        "고령화 구간": False
    },
    center={"lat": 35.8, "lon": 127.8}, # 대한민국 중심 좌표
    zoom=6,
    mapbox_style="white-bg"             # 배경 타일 없이 경계선만 표시
)

# 지도 레이아웃 조정 (여백 제거 및 배경 투명화)
fig.update_layout(
    margin={"r":0, "t":30, "l":0, "b":0},
    legend_title_text="고령화율 구간",
    height=650
)

# 스트림릿 화면에 지도 표시
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# 4. 고령화율 상위/하위 10개 시군구 표 나란히 표시
st.subheader("📋 고령화율 상위 & 하위 10개 지역")

col1, col2 = st.columns(2)

# 상위 10개 (고령화율이 가장 높은 지역)
top10 = sigungu_df.sort_values(by="고령화율", ascending=False).head(10)
top10_display = top10[["시도", "시군구", "고령화율", "전체인구", "고령인구"]].reset_index(drop=True)

# 하위 10개 (고령화율이 가장 낮은 지역)
bottom10 = sigungu_df.sort_values(by="고령화율", ascending=True).head(10)
bottom10_display = bottom10[["시도", "시군구", "고령화율", "전체인구", "고령인구"]].reset_index(drop=True)

with col1:
    st.markdown("🔴 **고령화율 가장 높은 10곳**")
    st.dataframe(top10_display, use_container_width=True)

with col2:
    st.markdown("🔵 **고령화율 가장 낮은 10곳**")
    st.dataframe(bottom10_display, use_container_width=True)
