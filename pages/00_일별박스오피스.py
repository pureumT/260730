from datetime import datetime, timedelta
import random
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="🍿 팝콘 타임머신 & 박스오피스",
    page_icon="🎬",
    layout="wide",
)

# ==========================================
# 2. API 키 및 공통 함수 (캐싱 적용)
# ==========================================
if "KOBIS_KEY" not in st.secrets:
    st.error(
        "🚨 **st.secrets['KOBIS_KEY']가 설정되지 않았습니다.** Secrets에 키를 입력해 주세요."
    )
    st.stop()

KOBIS_KEY = st.secrets["KOBIS_KEY"]
API_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"


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
        return None, f"네트워크 오류: {str(e)}"


# 기준 날짜 계산 (KST 어제)
today_kst = datetime.now(ZoneInfo("Asia/Seoul"))
default_yesterday = (today_kst - timedelta(days=1)).date()

# Session State를 이용한 날짜 상태 관리 (랜덤 타임머신 버튼용)
if "selected_date" not in st.session_state:
    st.session_state.selected_date = default_yesterday


# ==========================================
# 3. 🎯 최상단: 타이틀 & 날짜 선택 컨트롤러 (탭 밖으로 배치!)
# ==========================================
st.title("🍿 팝콘 타임머신 & 박스오피스 Hub")
st.caption("과거로 떠나는 영화 여행부터 꿀잼 데이터 분석까지!")

# 상단 제어바 (날짜 선택 + 타임머신 버튼)
ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 1, 1])

with ctrl_col1:
    # date_input의 상태를 session_state와 연동
    chosen_date = st.date_input(
        "📅 **조회할 날짜를 선택하세요**",
        value=st.session_state.selected_date,
        max_value=default_yesterday,
        key="date_picker",
    )
    st.session_state.selected_date = chosen_date

with ctrl_col2:
    st.write(" ")  # 정렬용 여백
    st.write(" ")
    # 🎲 랜덤 타임머신 버튼
    if st.button("🎲 **랜덤 타임머신!**", use_container_width=True):
        # 2004년 1월 1일 ~ 어제 사이 랜덤 날짜 뽑기
        start_date = datetime(2004, 1, 1).date()
        random_days = random.randint(0, (default_yesterday - start_date).days)
        st.session_state.selected_date = start_date + timedelta(
            days=random_days
        )
        st.rerun()

with ctrl_col3:
    st.write(" ")
    st.write(" ")
    if st.button("🔄 **어제로 돌아가기**", use_container_width=True):
        st.session_state.selected_date = default_yesterday
        st.rerun()

current_date = st.session_state.selected_date
target_dt = current_date.strftime("%Y%m%d")

st.markdown(
    f"### 📍 현재 탐색 중인 날짜: **{current_date.strftime('%Y년 %m월 %d일')}**"
)
st.divider()


# ==========================================
# 4. 데이터 로드 & 에러 체크
# ==========================================
df, err = fetch_box_office(target_dt)

if err:
    st.error(f"🚨 **{err}**")
    st.warning(
        "💡 Secrets의 KOBIS_KEY를 확인하거나 상단에서 다른 날짜를 선택해 보세요."
    )
    st.stop()


# ==========================================
# 5. 메인 콘텐츠 탭 구성
# ==========================================
tab1, tab2, tab3 = st.tabs(
    ["🥇 1위 하이라이트 & 추억", "📈 7일 흥행 추세 & 이슈", "📊 영화관 좌석 효율"]
)

# ------------------------------------------
# TAB 1: 1위 영화 하이라이트 & 생일 타임머신
# ------------------------------------------
with tab1:
    top = df.sort_values("rank").iloc[0]

    st.subheader(
        f"🏆 이 날의 챔피언: <{top['movieNm']}>", anchor=False
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎬 영화명", top["movieNm"])
    c2.metric("🍿 당일 관객수", f"{int(top['audiCnt']):,} 명")
    c3.metric("🎟️ 누적 관객수", f"{int(top['audiAcc']):,} 명")
    c4.metric("🖥️ 스크린수", f"{int(top['scrnCnt']):,} 개")

    # 재미 요소: SNS 자랑용 텍스트 복사 카드
    st.info(
        f"""
    📣 **[SNS 공유용 찰진 요약]**  
    "{current_date.strftime('%Y년 %m월 %d일')} 극장가는 **<{top['movieNm']}>**이(가) 점령했다!  
    하루 동안 무려 **{int(top['audiCnt']):,}명**이 이 영화를 보며 팝콘을 튀겼습니다 🍿"
    """
    )

    st.subheader("📋 순위 표")
    table = df[
        ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
    ].copy()
    table.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

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
# TAB 2: 흥행 추세 & 핫이슈 기상도
# ------------------------------------------
with tab2:
    st.subheader("🔥 극장가 핫이슈 기상도")

    # 역주행 영화 감지
    df["rankInten"] = df["rankInten"].astype(int)
    up_movies = df[df["rankInten"] > 0].sort_values(
        "rankInten", ascending=False
    )

    if not up_movies.empty:
        col_a, col_b = st.columns(2)
        with col_a:
            st.success("🚀 **역주행 급상승 영화**")
            for _, row in up_movies.iterrows():
                st.write(
                    f"- **{row['movieNm']}**: 전날 대비 **+{row['rankInten']}계단** (현재 {row['rank']}위)"
                )
    else:
        st.write("오늘은 큰 순위 변동 없이 평화로운 극장가입니다. ☕")

    st.divider()

    st.subheader(f"📈 선택 날짜 기준 7일간 TOP 5 흥행 추이")
    with st.spinner("과거 7일간 데이터를 불러오는 중..."):
        daily_dfs = []
        for i in range(6, -1, -1):
            past_date = current_date - timedelta(days=i)
            p_df, p_err = fetch_box_office(past_date.strftime("%Y%m%d"))
            if p_df is not None:
                p_df["date"] = past_date.strftime("%m-%d")
                daily_dfs.append(p_df)

    if daily_dfs:
        combined_df = pd.concat(daily_dfs, ignore_index=True)
        top5_movies = df.head(5)["movieNm"].tolist()
        filtered_df = combined_df[combined_df["movieNm"].isin(top5_movies)]
        pivot_df = filtered_df.pivot(
            index="date", columns="movieNm", values="audiCnt"
        ).fillna(0)
        st.line_chart(pivot_df)

# ------------------------------------------
# TAB 3: 상영 좌석 효율성 (가성비 영화)
# ------------------------------------------
with tab3:
    st.subheader("💡 알짜배기 영화 찾기 (1회 상영 당 관객수)")
    st.caption(
        "스크린 수가 적어도 관객이 꽉꽉 차는 실속파 영화를 확인해 보세요!"
    )

    df["audi_per_show"] = (df["audiCnt"] / df["showCnt"]).round(1)
    best_eff = df.sort_values("audi_per_show", ascending=False)

    top_eff_movie = best_eff.iloc[0]
    st.warning(
        f"🔥 **좌석 점유율 1위:** <{top_eff_movie['movieNm']}> (1회 상영당 평균 **{top_eff_movie['audi_per_show']}명** 관람!)"
    )

    st.bar_chart(best_eff.head(5).set_index("movieNm")["audi_per_show"])
