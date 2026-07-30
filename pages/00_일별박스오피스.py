from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

# ==========================================
# 1. 페이지 설정 및 기본 구성
# ==========================================
st.set_page_config(
    page_title="🎬 올인원 영화 박스오피스 Hub",
    page_icon="🍿",
    layout="wide",
)

st.title("🎬 올인원 영화 박스오피스 인사이트 Hub")
st.caption(
    "어제 박스오피스부터 과거 추억 탐색, 흥행 추세 및 스크린 효율 분석까지 한눈에 확인하세요."
)


# ==========================================
# 2. API 키 및 공통 함수 (캐싱 적용)
# ==========================================
# Secrets에서 API 키 확인
if "KOBIS_KEY" not in st.secrets:
    st.error(
        "🚨 **st.secrets['KOBIS_KEY']가 설정되지 않았습니다.** Secrets에 키를 입력해 주세요."
    )
    st.stop()

KOBIS_KEY = st.secrets["KOBIS_KEY"]
API_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"


# API 호출 함수 (속도 향상을 위해 캐싱 적용)
@st.cache_data(ttl=3600)
def fetch_box_office(target_dt_str):
    try:
        res = requests.get(
            API_URL,
            params={"key": KOBIS_KEY, "targetDt": target_dt_str},
            timeout=10,
        )
        if res.status_code != 200:
            return None, f"HTTP 오류 ({res.status_code})"

        data = res.json()

        if "faultInfo" in data:
            return (
                None,
                f"API 키 오류: {data['faultInfo'].get('message', '인증 실패')}",
            )

        box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
        if not box_list:
            return None, "해당 날짜의 데이터가 없습니다."

        df = pd.DataFrame(box_list)

        # 문자열 숫자를 정수형으로 변환
        num_cols = [
            "rank",
            "rankInten",
            "audiCnt",
            "audiAcc",
            "scrnCnt",
            "showCnt",
        ]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        return df, None
    except Exception as e:
        return None, f"네트워크 요청 오류: {str(e)}"


# 한국 시간(KST) 기준 어제 날짜 구하기
today_kst = datetime.now(ZoneInfo("Asia/Seoul"))
default_yesterday = (today_kst - timedelta(days=1)).date()

# ==========================================
# 3. 사이드바: 날짜 선택
# ==========================================
st.sidebar.header("🔍 조회 설정")
selected_date = st.sidebar.date_input(
    "조회할 날짜를 선택하세요",
    value=default_yesterday,
    max_value=default_yesterday,  # 오늘 이후 날짜는 선택 불가
)
target_dt = selected_date.strftime("%Y%m%d")

st.sidebar.info(f"선택된 날짜: **{selected_date.strftime('%Y년 %m월 %d일')}**")

# ==========================================
# 4. 3가지 탭 구성
# ==========================================
tab1, tab2, tab3 = st.tabs(
    ["📅 일별 순위 & 추억 탐색", "📈 7일간 흥행 추세", "📊 스크린 & 상영 효율"]
)

# ------------------------------------------
# TAB 1: 일별 순위 & 추억 탐색
# ------------------------------------------
with tab1:
    df, err = fetch_box_office(target_dt)

    if err:
        st.error(f"🚨 {err}")
        st.info(
            "💡 Secrets의 KOBIS_KEY 값을 확인하거나 다른 날짜를 선택해 보세요."
        )
    else:
        # 1위 영화 하이라이트
        top = df.sort_values("rank").iloc[0]
        st.subheader(f"🥇 {selected_date.strftime('%Y년 %m월 %d일')}의 1위 영화")

        col1, col2, col3 = st.columns(3)
        col1.metric("영화명", top["movieNm"])
        col2.metric("당일 관객수", f"{int(top['audiCnt']):,} 명")
        col3.metric("누적 관객수", f"{int(top['audiAcc']):,} 명")

        st.caption(
            f"💡 **추억 한 스푼:** {selected_date.strftime('%Y년 %m월 %d일')}에는 하루 동안 **{int(top['audiCnt']):,}명**의 관객이 <{top['movieNm']}>을(를) 관람했습니다!"
        )

        st.divider()

        # 전체 TOP 10 표
        st.subheader("📋 전체 박스오피스 TOP 10")

        table = df[
            ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
        ].copy()
        table.columns = [
            "순위",
            "영화명",
            "개봉일",
            "관객수",
            "누적관객",
            "스크린수",
        ]

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "순위": st.column_config.NumberColumn(format="%d위"),
                "관객수": st.column_config.NumberColumn(format="%d 명"),
                "누적관객": st.column_config.NumberColumn(format="%d 명"),
                "스크린수": st.column_config.NumberColumn(format="%d 개"),
            },
        )

# ------------------------------------------
# TAB 2: 7일간 흥행 추세
# ------------------------------------------
with tab2:
    st.subheader(
        f"📈 {selected_date.strftime('%Y-%m-%d')} 기준 최근 7일간 관객수 추이"
    )
    st.caption("선택한 날짜를 포함하여 이전 7일간의 TOP 5 영화 관객 변화입니다.")

    with st.spinner("7일간의 데이터를 수집 중입니다..."):
        daily_dfs = []
        for i in range(6, -1, -1):
            past_date = selected_date - timedelta(days=i)
            past_dt_str = past_date.strftime("%Y%m%d")
            p_df, p_err = fetch_box_office(past_dt_str)

            if p_df is not None:
                p_df["date"] = past_date.strftime("%m-%d")
                daily_dfs.append(p_df)

    if daily_dfs:
        combined_df = pd.concat(daily_dfs, ignore_index=True)

        # 기준일(선택 날짜) TOP 5 영화 기준으로 피벗 테이블 생성
        top5_movies = df.head(5)["movieNm"].tolist()
        filtered_df = combined_df[combined_df["movieNm"].isin(top5_movies)]

        pivot_df = filtered_df.pivot(
            index="date", columns="movieNm", values="audiCnt"
        ).fillna(0)

        # 꺾은선 그래프 연출
        st.line_chart(pivot_df)

        # 역주행 / 급상승 알리미
        st.subheader("🔥 전날 대비 순위 급상승(역주행) 영화")
        df["rankInten"] = df["rankInten"].astype(int)
        up_movies = df[df["rankInten"] > 0].sort_values(
            "rankInten", ascending=False
        )

        if not up_movies.empty:
            for _, row in up_movies.iterrows():
                st.success(
                    f"▲ **{row['movieNm']}**: 전날 대비 **{row['rankInten']}계단** 상승! (현재 {row['rank']}위)"
                )
        else:
            st.info("당일 순위가 크게 상승한 역주행 영화가 없습니다.")
    else:
        st.warning("7일간의 데이터를 불러오지 못했습니다.")

# ------------------------------------------
# TAB 3: 스크린 & 상영 효율 분석
# ------------------------------------------
with tab3:
    if not err and df is not None:
        st.subheader("📊 스크린 점유 및 좌석 효율성 분석")

        # 스크린 1개당 관객수 / 회당 관객수 계산
        df["audi_per_screen"] = (df["audiCnt"] / df["scrnCnt"]).round(1)
        df["audi_per_show"] = (df["audiCnt"] / df["showCnt"]).round(1)

        # 스크린 독과점 지수 (상위 3개 영화 스크린 점유율)
        total_screens = df["scrnCnt"].sum()
        top3_screens = df.head(3)["scrnCnt"].sum()
        top3_share = (
            (top3_screens / total_screens * 100) if total_screens > 0 else 0
        )

        c1, c2 = st.columns(2)
        c1.metric("TOP 10 총 스크린수", f"{int(total_screens):,} 개")
        c2.metric(
            "상위 3개 영화 스크린 점유율",
            f"{top3_share:.1f}%",
            help="TOP 10 영화가 확보한 전체 스크린 중 상위 3개 영화의 비중입니다.",
        )

        st.divider()

        # 회당 관객수(효율) 비교 차트
        st.write("🎬 **상영 1회당 평균 관객수 (체워진 좌석 효율성 TOP 5)**")
        eff_top5 = df.sort_values("audi_per_show", ascending=False).head(5)

        st.bar_chart(eff_top5.set_index("movieNm")["audi_per_show"])

        # 상세 데이터 표
        st.write("📋 **영화별 상세 스크린 효율 표**")
        analysis_table = df[
            [
                "rank",
                "movieNm",
                "scrnCnt",
                "showCnt",
                "audiCnt",
                "audi_per_show",
            ]
        ].copy()
        analysis_table.columns = [
            "순위",
            "영화명",
            "스크린수",
            "상영횟수",
            "관객수",
            "상영1회당 관객수",
        ]

        st.dataframe(
            analysis_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "상영1회당 관객수": st.column_config.NumberColumn(
                    format="%.1f 명"
                )
            },
        )
