from datetime import datetime, timedelta
import random
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(
    page_title="🍿 팝콘 타임머신 & 영화관 주식창",
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

        # 수치형 데이터 변환
        num_cols = [
            "rank",
            "rankInten",
            "salesAmt",
            "salesShare",
            "salesInten",
            "salesChange",
            "salesAcc",
            "audiCnt",
            "audiInten",
            "audiChange",
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


# KST 기준 어제 날짜
today_kst = datetime.now(ZoneInfo("Asia/Seoul"))
default_yesterday = (today_kst - timedelta(days=1)).date()

# ==========================================
# 3. 타임머신 상태 관리 (버그 완전 수정!)
# ==========================================
if "target_date" not in st.session_state:
    st.session_state.target_date = default_yesterday


# 날짜 변경 콜백 함수들
def set_random_date():
    start_date = datetime(2004, 1, 1).date()
    random_days = random.randint(0, (default_yesterday - start_date).days)
    st.session_state.target_date = start_date + timedelta(days=random_days)


def reset_to_yesterday():
    st.session_state.target_date = default_yesterday


def on_date_change():
    st.session_state.target_date = st.session_state.temp_date_picker


# ==========================================
# 4. 최상단 날짜 컨트롤러
# ==========================================
st.title("🍿 팝콘 타임머신 & 박스오피스 인사이트")
st.caption("어제 박스오피스부터 매출 떡상률, 티켓 단가 분석까지 한눈에!")

ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 1, 1])

with ctrl_col1:
    st.date_input(
        "📅 **조회할 날짜 선택**",
        value=st.session_state.target_date,
        max_value=default_yesterday,
        key="temp_date_picker",
        on_change=on_date_change,
    )

with ctrl_col2:
    st.write(" ")
    st.write(" ")
    st.button(
        "🎲 **랜덤 타임머신!**",
        on_click=set_random_date,
        use_container_width=True,
    )

with ctrl_col3:
    st.write(" ")
    st.write(" ")
    st.button(
        "🔄 **어제로 돌아가기**",
        on_click=reset_to_yesterday,
        use_container_width=True,
    )

current_date = st.session_state.target_date
target_dt = current_date.strftime("%Y%m%d")

st.markdown(
    f"### 📍 현재 탐색 일자: **{current_date.strftime('%Y년 %m월 %d일')}**"
)
st.divider()

# ==========================================
# 5. 데이터 로드 & 에러 체크
# ==========================================
df, err = fetch_box_office(target_dt)

if err:
    st.error(f"🚨 **{err}**")
    st.warning("💡 다른 날짜를 선택하거나 KOBIS_KEY 상태를 확인하세요.")
    st.stop()

# 파생 데이터 계산 (티켓 평균 단가 = 당일 매출액 / 관객수)
df["avg_ticket_price"] = (
    df["salesAmt"] / df["audiCnt"].replace(0, 1)
).round(0)

# ==========================================
# 6. 탭 구성
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🥇 1위 영화 & 신작 감지",
        "📈 극장가 주식창 (매출 떡상/떡락)",
        "💰 티켓 단가 & 스크린 효율",
        "🍕 매출 점유율 (파이 차트)",
    ]
)

# ------------------------------------------
# TAB 1: 1위 영화 & NEW/OLD 배지
# ------------------------------------------
with tab1:
    top = df.sort_values("rank").iloc[0]

    is_new = top["rankOldAndNew"] == "NEW"
    badge = (
        "✨ [NEW] 갓 개봉한 신작!" if is_new else "🏛️ [OLD] 차트를 지키는 흥행작"
    )

    st.subheader(f"🏆 이 날의 1위: <{top['movieNm']}> {badge}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎬 영화명", top["movieNm"])
    c2.metric("🍿 당일 관객수", f"{int(top['audiCnt']):,} 명")
    c3.metric(
        "💵 당일 매출액",
        f"{int(top['salesAmt'] / 10000):,} 만원",
        delta=f"{top['salesChange']:.1f}% (전일 대비)",
    )
    c4.metric("🎟️ 누적 관객수", f"{int(top['audiAcc']):,} 명")

    st.divider()

    st.subheader("📋 전체 박스오피스 TOP 10")

    display_df = df.copy()
    display_df["태그"] = display_df["rankOldAndNew"].apply(
        lambda x: "✨ NEW" if x == "NEW" else "OLD"
    )
    display_df["매출액(만원)"] = (display_df["salesAmt"] / 10000).astype(int)

    table = display_df[
        [
            "rank",
            "태그",
            "movieNm",
            "openDt",
            "audiCnt",
            "매출액(만원)",
            "salesShare",
        ]
    ]
    table.columns = [
        "순위",
        "구분",
        "영화명",
        "개봉일",
        "관객수",
        "당일 매출(만원)",
        "매출 점유율(%)",
    ]

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "순위": st.column_config.NumberColumn(format="%d위"),
            "관객수": st.column_config.NumberColumn(format="%d 명"),
            "당일 매출(만원)": st.column_config.NumberColumn(format="%d 만원"),
            "매출 점유율(%)": st.column_config.NumberColumn(format="%.1f %%"),
        },
    )

# ------------------------------------------
# TAB 2: 극장가 주식창
# ------------------------------------------
with tab2:
    st.subheader("📈 당일 매출액 변동률 TOP 5 (전일 대비)")
    st.caption("주식 창처럼 매출액이 급격히 떡상하거나 떡락한 영화입니다.")

    surge_df = df.sort_values("salesChange", ascending=False)
    top_surge = surge_df.iloc[0]
    top_drop = surge_df.iloc[-1]

    col_a, col_b = st.columns(2)

    with col_a:
        st.success(
            f"🚀 **오늘의 떡상왕:** <{top_surge['movieNm']}>\n\n"
            f"- 전일 대비 매출 증가율: **+{top_surge['salesChange']:.1f}%**\n"
            f"- 당일 매출: **{int(top_surge['salesAmt'] / 10000):,} 만원**"
        )

    with col_b:
        st.error(
            f"📉 **오늘의 떡락왕:** <{top_drop['movieNm']}>\n\n"
            f"- 전일 대비 매출 변동률: **{top_drop['salesChange']:.1f}%**\n"
            f"- 당일 매출: **{int(top_drop['salesAmt'] / 10000):,} 만원**"
        )

    st.divider()
    st.write("📊 **TOP 10 영화의 매출 변동률(%) 비교**")
    st.bar_chart(df.set_index("movieNm")["salesChange"])

# ------------------------------------------
# TAB 3: 티켓 단가 & 스크린 효율
# ------------------------------------------
with tab3:
    st.subheader("💡 이 영화 관객은 티켓값을 얼마씩 냈을까?")
    st.caption(
        "당일 매출액을 관객수로 나누어 '평균 티켓 단가'를 추정합니다. (IMAX, 4DX, 조조 할인 등 관람 유형 반영)"
    )

    pricy_df = df.sort_values("avg_ticket_price", ascending=False)
    top_pricy = pricy_df.iloc[0]

    st.info(
        f"💎 **티켓 단가 1위:** <{top_pricy['movieNm']}> → 평균 **{int(top_pricy['avg_ticket_price']):,}원** / 1인당\n\n"
        f"(IMAX나 특별관 비중이 높거나 주말/성인 관람객 비율이 높을수록 단가가 올라갑니다!)"
    )

    st.bar_chart(pricy_df.set_index("movieNm")["avg_ticket_price"])

# ------------------------------------------
# TAB 4: 매출 점유율 싹쓸이 현황 (파이 차트 적용!)
# ------------------------------------------
with tab4:
    st.subheader("🍕 영화관 돈 싹쓸이 현황 (salesShare)")
    st.caption("당일 영화관 전체 매출 중 각 영화가 차지한 파이(비율)입니다.")

    top3_share = df.head(3)["salesShare"].sum()

    col_x, col_y = st.columns([1, 2])

    with col_x:
        st.metric(
            "상위 3개 영화의 매출 점유율 합계",
            f"{top3_share:.1f}%",
            help="1~3위 영화가 전체 영화 시장 돈을 얼마나 독식했는지 보여줍니다.",
        )
        if top3_share >= 70:
            st.warning("⚠️ **경고:** 독과점이 심각한 상태입니다!")
        else:
            st.success("✅ 여러 영화가 고루 선전하고 있습니다.")

    with col_y:
        # Plotly를 활용한 도넛형 파이 차트 연출
        fig = px.pie(
            df,
            values="salesShare",
            names="movieNm",
            title="영화별 매출 점유율 (%)",
            hole=0.4,  # 도넛 스타일
        )
        fig.update_traces(
            textposition="inside", textinfo="percent+label"
        )
        st.plotly_chart(fig, use_container_width=True)
