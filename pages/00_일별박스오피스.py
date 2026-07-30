from datetime import datetime, timedelta
import random
import time
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
    page_title="🍿 팝콘 오락실 & 박스오피스", page_icon="🎬", layout="wide"
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

# 게임 세션 상태 초기화
if "target_date" not in st.session_state:
    st.session_state.target_date = default_yesterday
if "game_score" not in st.session_state:
    st.session_state.game_score = 0
if "game_combo" not in st.session_state:
    st.session_state.game_combo = 0


def set_random_date():
    start_date = datetime(2004, 1, 1).date()
    random_days = random.randint(0, (default_yesterday - start_date).days)
    st.session_state.target_date = start_date + timedelta(days=random_days)


def reset_date():
    st.session_state.target_date = default_yesterday


def on_date_change():
    st.session_state.target_date = st.session_state.temp_picker


# ==========================================
# 3. 최상단 컨트롤러
# ==========================================
st.title("🍿 팝콘 오락실 & 박스오피스 Hub")
st.caption("데이터 분석부터 극장가 미니게임까지 즐겨보세요!")

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
            "🎲 **랜덤 타임머신**",
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
    st.stop()

top = df.sort_values("rank").iloc[0]

# ==========================================
# 5. 🎮 탭 구성 (미니게임 강화!)
# ==========================================
tab1, tab2, tab3 = st.tabs(
    ["🎮 팝콘 오락실 (미니게임 2종)", "🏆 1위 영화 & 비주얼", "📊 순위 & 주식창"]
)

# ------------------------------------------
# TAB 1: 🎮 팝콘 오락실 (게임성 극대화!)
# ------------------------------------------
with tab1:
    st.subheader("🎮 팝콘 오락실에 오신 것을 환영합니다!")

    game_type = st.radio(
        "**놀고 싶은 게임을 선택하세요:**",
        ["🎰 1. 오늘의 영화 가차 (슬롯머신)", "🔥 2. 관객수 UP & DOWN 퀴즈"],
        horizontal=True,
    )

    st.write("---")

    # ------------------------------------
    # 게임 1: 슬롯머신 (뽑기)
    # ------------------------------------
    if "슬롯머신" in game_type:
        st.markdown("### 🎰 팝콘 영화 가차 (Slot Machine)")
        st.caption(
            "버튼을 누르면 슬롯이 돌아가며 박스오피스 TOP 10 중 1편이 무작위로 당첨됩니다!"
        )

        slot_col, res_col = st.columns([1, 2])

        with slot_col:
            st.image(
                "https://em-content.zobj.net/source/skype/289/slot-machine_1f3b0.png",
                width=120,
            )
            spin_btn = st.button(
                "🎰 **레버 당기기! (SPIN)**", use_container_width=True
            )

        with res_col:
            if spin_btn:
                # 슬롯머신 돌아가는 연출
                placeholder = st.empty()
                movies = df["movieNm"].tolist()

                for _ in range(12):
                    temp_movie = random.choice(movies)
                    placeholder.markdown(f"## 🌀 **[{temp_movie}]** ...")
                    time.sleep(0.08)

                # 최종 결과
                picked_row = df.sample(1).iloc[0]
                placeholder.empty()

                if picked_row["rank"] == 1:
                    st.balloons()
                    st.success(
                        f"🎉 **JACKPOT! 1위 영화가 당첨되었습니다!**\n\n### 🎬 <{picked_row['movieNm']}> (당일 관객수: {picked_row['audiCnt']:,}명)"
                    )
                else:
                    st.info(
                        f"✨ **당첨!** {picked_row['rank']}위 영화가 나왔습니다.\n\n### 🎬 <{picked_row['movieNm']}>"
                    )

                yt_query = urllib.parse.quote(f"{picked_row['movieNm']} 예고편")
                st.markdown(
                    f"👉 [▶️ **유튜브에서 이 영화 예고편 보기**](https://www.youtube.com/results?search_query={yt_query})"
                )

    # ------------------------------------
    # 게임 2: UP & DOWN 연속 퀴즈
    # ------------------------------------
    else:
        st.markdown("### 🔥 관객수 UP & DOWN 아케이드")
        st.caption(
            "선택한 날짜의 데이터를 바탕으로 문제를 풉니다. 콤보를 쌓아 최고 기록을 세워보세요!"
        )

        # 게임 스코어 보드
        sc1, sc2 = st.columns(2)
        sc1.metric("현재 점수", f"{st.session_state.game_score} 점")
        sc2.metric("🔥 연속 콤보", f"{st.session_state.game_combo} 회")

        st.write("---")

        # 2위 영화 vs 1위 영화 절반 관객수 비교 문제
        movie_1st = df.iloc[0]
        movie_2nd = df.iloc[1] if len(df) > 1 else df.iloc[0]

        half_1st_audi = movie_1st["audiCnt"] / 2
        actual_2nd_audi = movie_2nd["audiCnt"]

        st.markdown(
            f"**Q. 2위 영화 <{movie_2nd['movieNm']}>의 어제 관객수는 1위 영화 <{movie_1st['movieNm']}> 관객수 절반({int(half_1st_audi):,}명)보다 많을까요, 적을까요?**"
        )

        btn_col1, btn_col2 = st.columns(2)

        is_up = actual_2nd_audi > half_1st_audi

        if btn_col1.button("▲ **UP (더 많다!)**", use_container_width=True):
            if is_up:
                st.balloons()
                st.success(
                    f"⭕ **정답입니다!** (<{movie_2nd['movieNm']}> 관객수: {actual_2nd_audi:,}명)"
                )
                st.session_state.game_score += 10
                st.session_state.game_combo += 1
            else:
                st.error(
                    f"❌ **틀렸습니다!** (<{movie_2nd['movieNm']}> 관객수: {actual_2nd_audi:,}명)"
                )
                st.session_state.game_combo = 0

        if btn_col2.button("▼ **DOWN (더 적다!)**", use_container_width=True):
            if not is_up:
                st.balloons()
                st.success(
                    f"⭕ **정답입니다!** (<{movie_2nd['movieNm']}> 관객수: {actual_2nd_audi:,}명)"
                )
                st.session_state.game_score += 10
                st.session_state.game_combo += 1
            else:
                st.error(
                    f"❌ **틀렸습니다!** (<{movie_2nd['movieNm']}> 관객수: {actual_2nd_audi:,}명)"
                )
                st.session_state.game_combo = 0

# ------------------------------------------
# TAB 2: 🏆 1위 영화 & 비주얼
# ------------------------------------------
with tab2:
    st.subheader(f"🏆 {current_date.strftime('%Y-%m-%d')} 영예의 1위")

    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.markdown(f"### **<{top['movieNm']}>**")
        m1, m2 = st.columns(2)
        m1.metric("🍿 관객수", f"{int(top['audiCnt']):,} 명")
        m2.metric("💵 당일 매출액", f"{int(top['salesAmt']/10000):,} 만원")

        daum_query = urllib.parse.quote(f"영화 {top['movieNm']}")
        st.markdown(
            f"👉 [🔍 **포스터 & 줄거리 보러가기**](https://search.daum.net/search?w=tot&q={daum_query})"
        )

    with col_right:
        fig_pie = px.pie(
            df,
            values="salesShare",
            names="movieNm",
            title="🎬 당일 시장 점유율 파이",
            hole=0.4,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

# ------------------------------------------
# TAB 3: 📊 순위 & 주식창
# ------------------------------------------
with tab3:
    st.subheader("📋 전체 박스오피스 TOP 10")
    st.dataframe(
        df[["rank", "movieNm", "openDt", "audiCnt", "salesShare"]].rename(
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
