from datetime import datetime, timedelta
import random
import urllib.parse
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ==========================================
# 1. 페이지 테마 & 기본 설정
# ==========================================
st.set_page_config(
    page_title="🍿 팝콘 랩 (Popcorn Lab)",
    page_icon="🎬",
    layout="wide",
)

# 커스텀 CSS로 UI 스타일링 강화
st.markdown(
    """
    <style>
    .stButton>button {
        border-radius: 12px;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 2. API 키 및 공통 데이터 불러오기
# ==========================================
if "KOBIS_KEY" not in st.secrets:
    st.error("🚨 Secrets에 `KOBIS_KEY`를 등록해 주세요!")
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
            return None, data["faultInfo"].get("message", "인증 오류")

        box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
        if not box_list:
            return None, "해당 날짜의 데이터가 없습니다."

        df = pd.DataFrame(box_list)
        num_cols = [
            "rank",
            "rankInten",
            "salesAmt",
            "salesShare",
            "salesChange",
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


# KST 어제 날짜
today_kst = datetime.now(ZoneInfo("Asia/Seoul"))
default_yesterday = (today_kst - timedelta(days=1)).date()

# 상태 관리 (날짜, 퀴즈, 한줄평)
if "target_date" not in st.session_state:
    st.session_state.target_date = default_yesterday
if "comments" not in st.session_state:
    st.session_state.comments = [
        ("익명 팝콘", "이날 1위 영화 영화관에서 진짜 재미있게 봄! 🍿"),
        ("영화덕후", "매출 점유율 독식 보소 ㄷㄷ"),
    ]


def set_random_date():
    start_date = datetime(2004, 1, 1).date()
    random_days = random.randint(0, (default_yesterday - start_date).days)
    st.session_state.target_date = start_date + timedelta(days=random_days)


def reset_date():
    st.session_state.target_date = default_yesterday


def on_date_change():
    st.session_state.target_date = st.session_state.temp_picker


# ==========================================
# 3. 🎯 UX 개편: 히어로 헤더 & 컨트롤 패널
# ==========================================
st.title("🍿 팝콘 랩 (Popcorn Lab)")
st.caption("과거 영화 탐색부터 꿀잼 퀴즈, 실시간 데이터 분석까지!")

with st.container():
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.date_input(
            "📅 **타임머신 날짜 선택**",
            value=st.session_state.target_date,
            max_value=default_yesterday,
            key="temp_picker",
            on_change=on_date_change,
        )
    with c2:
        st.write(" ")
        st.write(" ")
        st.button(
            "🎲 **랜덤 과거로!**",
            on_click=set_random_date,
            use_container_width=True,
        )
    with c3:
        st.write(" ")
        st.write(" ")
        st.button(
            "🔄 **어제로 복귀**", on_click=reset_date, use_container_width=True
        )

current_date = st.session_state.target_date
target_dt = current_date.strftime("%Y%m%d")

st.divider()

# ==========================================
# 4. 데이터 로드
# ==========================================
df, err = fetch_box_office(target_dt)

if err:
    st.error(f"🚨 {err}")
    st.warning("다른 날짜를 선택하거나 API 키를 확인하세요.")
    st.stop()

# 파생 데이터
df["avg_price"] = (df["salesAmt"] / df["audiCnt"].replace(0, 1)).round(0)
top = df.sort_values("rank").iloc[0]

# ==========================================
# 5. 🌟 메인 비주얼 UX: 1위 영화 카드 & 예고편
# ==========================================
st.subheader(f"🏆 {current_date.strftime('%Y-%m-%d')} 영예의 1위")

col_left, col_right = st.columns([1, 1])

with col_left:
    is_new = top["rankOldAndNew"] == "NEW"
    badge = "✨ NEW! 갓 개봉한 신작" if is_new else "🏛️ OLD 흥행 유지작"

    st.markdown(f"### **<{top['movieNm']}>**")
    st.caption(f"태그: {badge} | 개봉일: {top['openDt']}")

    m1, m2 = st.columns(2)
    m1.metric("🍿 관객수", f"{int(top['audiCnt']):,} 명")
    m2.metric(
        "💵 당일 매출액",
        f"{int(top['salesAmt']/10000):,} 만원",
        delta=f"{top['salesChange']:.1f}%",
    )

    # 🔗 외부 미디어 연동 UX (유튜브 예고편 / 다음 영화 검색)
    yt_query = urllib.parse.quote(f"{top['movieNm']} 예고편")
    daum_query = urllib.parse.quote(f"영화 {top['movieNm']}")

    st.markdown(
        f"""
    👉 [▶️ **유튜브에서 예고편 보기**](https://www.youtube.com/results?search_query={yt_query})  
    👉 [🔍 **다음 영화에서 포스터/정보 보기**](https://search.daum.net/search?w=tot&q={daum_query})
    """
    )

with col_right:
    # 파이 차트로 매출 독과점 직관적 시각화
    fig_pie = px.pie(
        df,
        values="salesShare",
        names="movieNm",
        title="🎬 당일 시장 점유율 파이",
        hole=0.4,
    )
    fig_pie.update_layout(
        margin=dict(t=30, b=0, l=0, r=0), height=220, showlegend=False
    )
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# ==========================================
# 6. 🎮 꿀잼 기능 모음 (탭 구성)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📊 전체 순위 & 주식창",
        "🎯 미니게임: 티켓값 맞추기",
        "💬 실시간 한줄평 코너",
        "💡 스크린/티켓 단가 분석",
    ]
)

# ------------------------------------------
# TAB 1: 순위 & 주식창 (UX 가독성 개선)
# ------------------------------------------
with tab1:
    st.subheader("📈 당일 극장가 주식창 (매출 변동률)")

    surge_df = df.sort_values("salesChange", ascending=False)
    up = surge_df.iloc[0]
    down = surge_df.iloc[-1]

    c_u, c_d = st.columns(2)
    c_u.success(
        f"🚀 **오늘의 떡상:** <{up['movieNm']}> (전일 대비 +{up['salesChange']:.1f}%)"
    )
    c_d.error(
        f"📉 **오늘의 떡락:** <{down['movieNm']}> (전일 대비 {down['salesChange']:.1f}%)"
    )

    st.subheader("📋 전체 박스오피스 TOP 10")
    disp = df.copy()
    disp["구분"] = disp["rankOldAndNew"].apply(
        lambda x: "✨ NEW" if x == "NEW" else "OLD"
    )
    disp["매출(만원)"] = (disp["salesAmt"] / 10000).astype(int)

    st.dataframe(
        disp[
            [
                "rank",
                "구분",
                "movieNm",
                "openDt",
                "audiCnt",
                "매출(만원)",
                "salesShare",
            ]
        ].rename(
            columns={
                "rank": "순위",
                "movieNm": "영화명",
                "openDt": "개봉일",
                "audiCnt": "관객수",
                "salesShare": "점유율(%)",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

# ------------------------------------------
# TAB 2: 🎮 미니게임 (참여형 컨텐츠)
# ------------------------------------------
with tab2:
    st.subheader("🎯 1위 영화 티켓 단가 맞추기 미니게임!")
    st.caption(
        f"선택한 날짜(<{top['movieNm']}>)의 **1인당 평균 티켓값**은 얼마였을까요?"
    )

    actual_price = int(top["avg_price"])

    user_guess = st.number_input(
        "예상하는 티켓 가격을 입력하세요 (원):",
        value=10000,
        step=500,
    )

    if st.button("정답 확인하기! 🎲"):
        diff = abs(user_guess - actual_price)
        if diff == 0:
            st.balloons()
            st.success(
                f"🎉 **대박! 완벽한 정답입니다!** 실제 평균 단가: **{actual_price:,}원**"
            )
        elif diff <= 1000:
            st.success(
                f"👏 **아까워요! 거의 맞췄습니다.** 실제 평균 단가: **{actual_price:,}원** (오차 {diff:,}원)"
            )
        else:
            st.warning(
                f"😅 **틀렸습니다!** 실제 평균 단가: **{actual_price:,}원** (차이: {diff:,}원)"
            )

# ------------------------------------------
# TAB 3: 💬 실시간 한줄평 (커뮤니티 요소)
# ------------------------------------------
with tab3:
    st.subheader(f"💬 {current_date.strftime('%Y-%m-%d')} 극장가 한줄평")

    # 댓글 입력폼
    with st.form("comment_form", clear_on_submit=True):
        nickname = st.text_input("닉네임", value="익명 팝콘")
        comment_text = st.text_input("한줄평을 남겨보세요!")
        submitted = st.form_submit_button("등록하기 🚀")

        if submitted and comment_text:
            st.session_state.comments.insert(0, (nickname, comment_text))
            st.rerun()

    st.write("---")
    # 댓글 목록 출력
    for nick, text in st.session_state.comments[:10]:
        st.markdown(f"**👤 {nick}**: {text}")

# ------------------------------------------
# TAB 4: 티켓 단가 & 스크린 분석
# ------------------------------------------
with tab4:
    st.subheader("💡 영화별 1인당 평균 티켓 단가 (원)")
    st.caption(
        "IMAX/4DX 등 특별관 비율이 높거나 성인 관람객 비중이 높으면 단가가 올라갑니다."
    )

    st.bar_chart(df.set_index("movieNm")["avg_price"])
