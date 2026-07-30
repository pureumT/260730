import streamlit as st
from openai import OpenAI

# 페이지 기본 설정 (멋진 타이틀과 로고)
st.set_page_config(page_title="AI Cyber Teacher", page_icon="⚡", layout="wide")

# 비밀 금고(secrets)에서 API 키를 꺼내 접속 준비
client = OpenAI(
    api_key=st.secrets["SOLAR_API_KEY"],
    base_url="https://api.upstage.ai/v1",
)

# ---------------------------------------------------------
# [사이드바] 캐릭터 선택 및 가젯(Gadget) 모듈
# ---------------------------------------------------------
with st.sidebar:
    st.title("⚡ SYSTEM CONTROL")
    st.caption("AI 프롬프트 페르소나 및 세션 옵션")
    
    # 1. 멋진 페르소나 선택
    persona = st.radio(
        "🎭 AI 페르소나 모드",
        ["🤖 친절한 미래 정보 스승", "🥷 츤데레 천재 해커", "🧙‍♂️ 알키미아(연금술) 마법사"]
    )
    
    st.divider()

    # 페르소나별 퓨샷(Few-shot) 프롬프트 정의
    if persona == "🤖 친절한 미래 정보 스승":
        SYSTEM_PROMPT = """너는 futuristic한 미래 지식을 친절하게 가르쳐주는 최고 레벨의 정보 선생님이야.
어려운 기술 용어를 완벽하고 명쾌한 비유를 들어 설명해 줘.

[답변 예시]
Q: RAM이 뭐야?
A: RAM은 최첨단 '광속 작업대'와 같아요! 작업대가 넓을수록 여러 프로젝트 설계도를 동시에 펼쳐놓고 빠르게 작업할 수 있죠.

Q: 방화벽이 뭐야?
A: 방화벽은 요새의 '스마트 보안 검문소'입니다. 허가되지 않은 수상한 데이터 패킷이 들어오면 즉시 차단하여 시스템을 보호하죠."""

    elif persona == "🥷 츤데레 천재 해커":
        SYSTEM_PROMPT = """너는 실력은 최고지만 말투는 무심하고 쿨한 '해커'야.
투덜대면서도 해답은 완벽하게 쉬운 비유로 핵심만 딱 짚어 줘.

[답변 예시]
Q: RAM이 뭐야?
A: 쯧, 그것도 몰라? RAM은 그냥 '책상 넓이'야. 책상이 넓어야 창을 여러 개 띄워도 안 버벅거리지. 이 정도는 기본이라고.

Q: 방화벽이 뭐야?
A: 해킹 막는 클럽 '문지기' 몰라? 해로운 놈들은 밖으로 쫓아내고 안전한 데이터만 통과시키는 게 방화벽이야."""

    else: # 연금술 마법사
        SYSTEM_PROMPT = """너는 디지털 세계의 원리를 마법의 언어로 풀어서 가르쳐주는 '전설의 연금술 스승'이다.
신비롭지만 깨달음을 주는 비유로 연금술(정보과학)의 비기를 전수해라.

[답변 예시]
Q: RAM이 뭐야?
A: RAM은 현자가 주문을 읊는 '찰나의 마법진'이니라! 마법진의 크기가 클수록 더욱 강력하고 많은 주문을 동시에 유지할 수 있지.

Q: 방화벽이 뭐야?
A: 그것은 데이터의 성소를 지키는 '결계(結界)'이니라. 사악한 마력의 침입을 물리쳐 성소를 정화하는 구실을 하지."""

    # 2. 세션 제어 기능 (초기화 & 다운로드)
    if st.button("🔄 대화 메모리 리셋", use_container_width=True):
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.rerun()

    # 대화 기록 텍스트 파일 다운로드
    if "messages" in st.session_state and len(st.session_state.messages) > 1:
        chat_text = "\n\n".join([f"[{m['role'].upper()}]\n{m['content']}" for m in st.session_state.messages if m['role'] != 'system'])
        st.download_button("📥 로그 기록 추출 (.txt)", data=chat_text, file_name="cyber_teacher_log.txt", use_container_width=True)

# ---------------------------------------------------------
# [메인 화면] 메인 챗 인터페이스
# ---------------------------------------------------------
st.title(f"⚡ {persona.split()[1]} 모드 가동 중")
st.caption("질문을 던지면 AI가 실시간 파동 스트리밍으로 답변을 출력합니다.")

# 대화 세션 초기화 (처음 접속 시)
if "messages" not in st.session_state or st.session_state.messages[0]["content"] != SYSTEM_PROMPT:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# 이전 대화 렌더링
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 퀵 추천 질문 (초반 쿨감용 버튼)
st.write("")
st.markdown("##### 💡 **Quick Query (클릭하여 즉시 질문):**")
q_col1, q_col2, q_col3 = st.columns(3)

prompt_to_send = None
if q_col1.button("🧠 CPU vs RAM 차이"):
    prompt_to_send = "CPU와 RAM의 차이를 너의 스타일로 가장 멋지게 설명해 줘!"
if q_col2.button("🛡️ 바이러스와 백신"):
    prompt_to_send = "컴퓨터 바이러스와 백신의 원리를 쉽게 설명해 줘!"
if q_col3.button("🌐 인터넷의 원리"):
    prompt_to_send = "우리가 웹사이트에 접속할 때 일어나는 일을 설명해 줘!"

# 채팅 입력창
user_input = st.chat_input("시스템에 질문을 입력하십시오...")

# 버튼 클릭 또는 일반 입력 처리
final_input = prompt_to_send or user_input

if final_input:
    # 사용자 입력 저장 및 출력
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"):
        st.markdown(final_input)

    # AI 스트리밍 응답 생성
    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model="solar-open2",
                messages=st.session_state.messages,
                reasoning_effort="none",
                stream=True,
            )
            answer = st.write_stream(
                chunk.choices[0].delta.content or ""
                for chunk in stream if chunk.choices
            )
            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception:
            st.error("⚠️ 시스템 통신 오류 발생. 잠시 후 다시 시도하십시오.")
