import streamlit as st
from datetime import date, datetime, timedelta
import holidays
import pytz
from ui import generate_rainy_calendar_html
from logic import is_business_day, get_time_range_for_today, get_seoul_today, daterange, check_bipo_status, process_dates_with_threadpool
from api import fetch_rain_data
from auth import get_auth_key, test_auth_key, save_auth_key, is_admin
from config import Config
import streamlit.components.v1 as components
from time_ridibooks import get_ridibooks_server_time, RidiTimeCounter
from ui_jason import render_rain_data_tab

st.set_page_config(page_title="☔ 비포", layout="centered")

def run_app():
    # 세션 상태 초기화
    if "retry_auth" not in st.session_state:
        st.session_state.retry_auth = False
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    st.title("☔ 오늘의 비포")

    # 인증키 불러오기
    auth_key, auth_ok = get_auth_key(retry=st.session_state.retry_auth)

    # 인증 및 관리자 UI
    if not (auth_ok or st.session_state.admin_authenticated):
        if st.session_state.retry_auth and not auth_key:
            st.warning(
                "⚠️ LocalStorage에서 인증키를 불러오지 못했습니다. "
                "인증키를 입력하거나 다시 불러오기 버튼을 눌러주세요."
            )

        with st.form("combined_auth_form"):
            key_input = st.text_input("🔑 API 인증키 입력", type="password", key="api_key_input")
            admin_input = st.text_input("⚜️ Admin", type="password", key="admin_password_input")
            submitted = st.form_submit_button("🔐 인증 및 저장")

        if submitted:
            admin_token = st.secrets.get("admin_token", "")
            if admin_input == admin_token:
                st.session_state.admin_authenticated = True
                st.session_state.auth_ok = True
                st.session_state.auth_key = st.secrets.get("API_KEY", "")
                st.success("⚜️ 관리자 인증 성공")
                st.rerun()
            elif key_input and test_auth_key(key_input):
                st.session_state.auth_key = key_input
                st.session_state.auth_ok = True
                save_auth_key(key_input)
                st.success("✅ 인증 성공! 인증키를 localstorage에 저장합니다.")
            else:
                st.session_state.auth_ok = False
                if admin_input and admin_input != admin_token:
                    st.error(
                        "⚠️ 관리자 비밀번호가 틀렸습니다."
                        " 관리자가 아니라면 API 인증키를 사용하세요."
                    )
                elif key_input and not test_auth_key(key_input):
                    st.error(
                        "❌ API 인증키가 올바르지 않습니다."
                        " 다시 입력하거나 정확한 API 인증키를 입력해주세요."
                    )
                else:
                    st.error("⚠️ 인증 정보가 입력되지 않았습니다. 다시 시도해주세요.")

        # localStorage 재불러오기 버튼
        if not auth_ok and st.button("🔄 API 인증키 LocalStorage에서 다시 불러오기"):
            auth_key, auth_ok = get_auth_key(retry=True)
            st.session_state.auth_key = auth_key
            st.session_state.auth_ok = auth_ok
            if not auth_ok:
                st.warning(
                    "⚠️ LocalStorage에서 인증키를 불러오지 못했습니다. "
                    "인증키를 입력하거나 다시 불러오기 버튼을 눌러주세요."
                )
        with st.expander("API 발급 및 인증 안내"):
            st.markdown("## 1. 기상청 API 허브 접속")
            st.image("https://i.imgur.com/5fuACIL.png", use_container_width=True)
            st.info("기상청 API허브: https://apihub.kma.go.kr/")
            st.markdown(
                "[기상청 API허브] - [인기 API] - [AWS 매분자료]  \n"
                "(로그인 혹은 회원가입을 선행하세요.)"
            )
            st.markdown("## 2. AWS 매분자료 API 발급")
            st.image("https://i.imgur.com/X6n7ILh.png", use_container_width=True)
            st.markdown(
                "[1. AWS 매분자료 조회] - 우측[API 활용신청]  \n"
                "신청 사유는 개인 사정에 알맞게 작성해주세요. 발급까지 약간의 시간이 소요될 수 있습니다."
            )
        st.stop()

    # 인증 완료 후 앱 본문 진행
    if not (st.session_state.get("auth_ok") or st.session_state.get("admin_authenticated")):
        st.stop()

    now = datetime.now(pytz.timezone("Asia/Seoul"))
    one_min_ago = now - timedelta(minutes=1)
    formatted_now = f"{one_min_ago.strftime('%Y-%m-%d')} | {one_min_ago.strftime('%H:%M')} | 서울"

    tabs = st.tabs(["오늘의 비포", "About","Ridi", "Statics", "Admin"])
    with tabs[0]:
        view_option = st.radio("옵션 선택", ["Today", "Month"], horizontal=True)

        if view_option == "Today":
            if st.button("조회"):
                today = get_seoul_today()
                kr_holidays = holidays.KR(years=[today.year])

                if not is_business_day(today, kr_holidays):
                    st.info("주말, 공휴일, 5월 1일은 비포가 없습니다.")
                else:
                    now_hhmm = now.strftime("%H%M")
                    st.write(f"조회 기준시간: {formatted_now}")

                    if now_hhmm < Config.TIME_START:
                        st.info(f"⏳ 아직 {int(Config.TIME_START[:2])}시가 되지 않았습니다.")
                    else:
                        time_start, time_end = get_time_range_for_today(today)
                        st.write(f"비포 시간범위: {time_start} ~ {time_end}")
                        
                        df = fetch_rain_data(today, auth_key, time_start, time_end)
                        status, rain_times = check_bipo_status(today, df, kr_holidays, time_end)

                        if status == "rain_detected":
                            st.success("💧 오늘은 비포 받는 날!")

                            with st.expander("📍 비가 온 시간 목록 보기"):
                                for t in rain_times:
                                    st.write(f"💧 {today.strftime('%Y-%m-%d')} | {t}")
                                    
                        elif status == "no_rain":
                            st.warning("😞 현재 기준 비포가 없습니다.")
                        elif status == "pass":
                            st.info("⛱️ 오늘은 비포 대상일이 아닙니다.")
                        else:
                            st.error("⚠️ 비포 여부를 확인할 수 없습니다. (API 오류 등)")

        elif view_option == "Month":
            today = date.today()
            start_of_month = today.replace(day=1)

            with st.form("month_bipo_form"):
                start_date = st.date_input("조회 시작일", value=start_of_month)
                end_date = st.date_input("조회 종료일", value=today, max_value=today)
                submitted = st.form_submit_button("조회 시작")

            if submitted:
                if start_date > end_date:
                    st.error("시작 날짜가 종료 날짜보다 빨라야 합니다.")
                elif end_date > today:
                    st.error("종료 날짜는 오늘 날짜를 넘을 수 없습니다.")
                else:
                    with st.spinner("조회 중입니다... 잠시만 기다려주세요."):
                        dates = list(daterange(start_date, end_date))
                        kr_holidays = holidays.KR(years=list(range(start_date.year, end_date.year + 1)))
                        now_time = datetime.now(pytz.timezone("Asia/Seoul")).time()

                        valid_dates = [
                            d for d in dates
                            if is_business_day(d, kr_holidays)
                            and (d != today or now_time >= Config.TIME_START_OBJ)
                        ]

                        result_by_status = process_dates_with_threadpool(valid_dates, auth_key, kr_holidays)

                        rain_days = result_by_status.get("rain_detected", [])
                        fail_days = result_by_status.get("fail", [])

                        st.write(f"조회 기준시간: {formatted_now}")
                        st.write(f"💧 비포 있는 날: {len(rain_days)}일")
                        st.write(f"⚠️ API 조회 실패: {len(fail_days)}일")

                        html_content = generate_rainy_calendar_html(start_date, end_date, result_by_status)
                        st.components.v1.html(html_content, height=600, scrolling=True)

    with tabs[1]:
        st.title("📓 앱 소개")
        st.markdown(
            """
            ### 1. Ridi 비/눈 포인트 조건
            <span style="background-color:powderblue">🔗 Ridi | [눈비오는날 포인트 받는 법](https://ridihelp.ridibooks.com/support/solutions/articles/154000207820)</span>
            * ⏰ 시간: 평일 `10:00 ~ 16:00`
            * 📍 장소: 리디가 있는 `선릉역`에 💧/❄️이 오면
            * ⭐ 혜택: 당일 `18:00`에 선착순 `1,000`포인트!
            * 💳 자동충전: 월 `1만원` 이상 자동충전 시 `최대 5회` 자동알림
            ---
            """,
            unsafe_allow_html=True
        )
        with st.expander("Details"):
            st.markdown(
                """
                * **시간**: <span style="background-color: #EEE; color: #666; font-weight:bold;">10:00 ~ 16:00</span>
                    * 주말, 공휴일, 근로자의 날(5/1) 제외
    
                * **장소**: 선릉역 (기상청 공고 기준)
                    * ~~공식은 아니지만~~ 강남구 일원동 기상청 기준
    
                * **혜택**: 당일 <span style="background-color: #EEE; color: #666; font-weight:bold;">18:00</span>에 선착순 1,000포인트
                    * `도서장르` → `추천` → `이벤트 배너` 접속 후 포인트 받기
                    * 선착순 3,000명
                    * 당일 `23:59`까지 사용 가능 (이후 소멸)
                    * 자동충전 시에도 선착순 참여 가능 (성공 시 총 2,000 포인트)
    
                * **자동충전**: 월 <span style="background-color: #EEE; color: #666; font-weight:bold;">1만원</span> 이상 자동충전 시 <span style="background-color: #EEE; color: #666; font-weight:bold;">최대 5회회</span> 자동알림
                    * 알림을 클릭해야 자동알림 포인트 수령 가능 (1,000 포인트)
                    * 매월 1~3일 충전 시 더블 포인트 적립
                        * 다음달 1일 9:30부터 자동충전
                        * 당월 비포 혜택 받으려면 `지금 충전하기` 옵션 선택
                        * 당일 비포 혜택 받으려면 `16:00` 전에 결제
                        * 자동결제 취소 시 혜택 제외됨
                    * **최대 5회 규칙**
                        * 무조건 `월 강수 횟수`가 기준 (이후에는 선착순만 참여 가능)
                        ```
                        * Q1: 이번달 6번째 비인데 자동알림이 안 와요  
                          A1: 5번째까지만 자동지급
                        * Q2: 자동충전 전 그 달에 비가 2번 왔어요!  
                          A2: 앞으로 3번 자동지급
                        * Q3: 자동알림을 한번 놓쳤는데 6번째에 알림이 오나요?  
                          A3: ㄴㄴ, 월 강수가 기준이므로 6번째는 자동알림이 없고 선착순만 가능
                        ```
                """,
                unsafe_allow_html=True
            )
    
        st.markdown("### 2. 앱 이용방법")
        with st.expander("Details"):
            st.markdown(
                """
                1. **오늘의 비포**
                   - Today: 10:00 ~ 현재 시각(분-1) 구간의 비포 여부 조회
                   - Month: 선택 기간 동안 비포를 캘린더 형식으로 조회
                     - 조회 종료일은 오늘로 기본 설정
                     - 오늘은 10:00 ~ 현재 시각(분-1) 실시간 반영
                     - 최근 31일 이내면 2번째 조회부터 캐시 사용으로 조회 속도 향상
                     - API 조회 실패한 날은 여러 번 재시도 하면 조회됨, 차후 성공 시 캐시에 저장
                     - 캐시 데이터는 6시간 동안 유효
                   - 색상 표시
                     > 초록: 오늘 비 옴  
                     > 빨강: 오늘 비 안 옴  
                     > 파랑: 과거 비 내린 날  
                     > 옅은 회색: 조회 기간 외  
                     > 진한 회색: API 조회 실패
    
                2. **About**
                   - 비/눈 포인트 조건 및 앱 이용 방법 안내
    
                3. **Ridi**
                   - Ridi 서버시간 조회 및 새로고침 기준 시간 설정
                   - 실시간 서버시간 조회 버튼 제공
                   - 이벤트 배너 위치 자동 이동 링크 포함
    
                4. **Statics**
                   - 기간별 비/눈 통계 그래프 제공
    
                5. **Admin**
                   - 관리자 전용 기능
                   - 일반 사용자 접근 불가, 사용 자제 권장
                """,
                unsafe_allow_html=True
            )
    
        st.markdown("### 3. 앱 이용 시 주의사항")
        with st.expander("Details"):
            st.markdown(
                """
                #### 1. 서비스 형태 안내
                - 본 서비스는 웹/앱으로 제공됩니다.
                - **별도 설치하는 독립형 앱이 아닙니다.**
                - 모바일, 데스크톱 등 다양한 환경의 **웹 브라우저**에서 접속하여 사용합니다.
    
                #### 2. 인증키 저장 위치 및 방식
                - API 인증키를 일일이 입력하지 않도록 저장합니다.
                - API 인증키는 **브라우저의 LocalStorage**에 저장되며, 서버 전송 또는 저장하지 않습니다.
                - LocalStorage는 브라우저 내 저장 공간으로, 인증키가 기기에 브라우저별로 저장됩니다.
                  따라서 공용 모바일 기기에서는 인증키 유출 위험이 있습니다.
                - **모바일/PC 모두 작동**됩니다.
                - 앱 또는 브라우저를 완전히 종료해도 인증키는 유지되지만,
                  시크릿 모드에서는 창을 닫으면 인증키가 삭제됩니다.
                    
                #### 3. LocalStorage 동작 특성
                | 상황            | 인증키 유지 여부           | 설명                          |
                |-----------------|--------------------------|-----------------------------|
                | **일반 모드**     | 탭/앱 종료 후에도 유지       | 브라우저 캐시 내 인증키 유지        |
                | **시크릿 모드**   | 창(탭) 닫으면 삭제          | 새로고침은 유지되나, 시크릿 종료 시 삭제  |
    
                #### 4. 인증키 관리 주의사항
                - 인증키는 **타인에게 절대 공유하지 마세요**.
                - 인증키 무단 사용 시 서비스 이용에 제한이 생길 수 있습니다.
    
                #### 5. Admin 안내
                - 일반 사용자는 Admin에 진입할 수 없습니다.
                - Admin 권한으로 인한 추가 기능은 별도 관리용입니다.
    
                #### 6. 기상청 API 및 데이터 조회 안내
                - 조회 대상: **강남구 일원동 10:00~16:00 1분 단위 강수 데이터**
                  1분이라도 강수 있으면 ‘비 있음’
                - 조회 시점 기준 **현재 시각 1분 전까지의 데이터만 조회**합니다.
                  기상청 API는 미래 시점 데이터도 포함할 수 있어, 조회 시점 바로 전 시점까지 데이터를 조회합니다.
                """,
                unsafe_allow_html=True
            )
    
    
    with tabs[2]:
        st.title(" ⏰ Ridi 서버시간")
        st.info("🔗 Ridi | https://ridibooks.com/ebook/recommendation")

        if "ridi_server_time" not in st.session_state:
            st.session_state.ridi_server_time = get_ridibooks_server_time()
            st.session_state.ridi_time_counter = RidiTimeCounter(st.session_state.ridi_server_time)
        
        base_time = st.session_state.ridi_time_counter.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        st.write(f"🕰️새로고침 기준시간: `{base_time}`")
        
        components.html(f"""
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 150px;">
                <div id="date" style="font-size:18px; color: #555;"></div>
                <div id="clock" style="font-size:48px; font-weight:bold; margin-top: 5px;"></div>
            </div>
            <script>
            const start = new Date("{st.session_state.ridi_time_counter.now().isoformat()}");
            const startPerf = performance.now();

    
        function updateClock() {{
                const clockEl = document.getElementById("clock");
                const dateEl = document.getElementById("date");
                if (!clockEl || !dateEl) return;
        
                const elapsed = performance.now() - startPerf;
                const current = new Date(start.getTime() + elapsed);
        
                const dateStr = current.toLocaleDateString('ko-KR', {{
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    weekday: 'short'
                }});
                const timeStr = current.toLocaleTimeString('sv-SE', {{ hour12:false }}) +
                                '.' + current.getMilliseconds().toString().padStart(3, '0');

                dateEl.innerText = dateStr;
                clockEl.innerText = timeStr;
            }}
        
            setInterval(updateClock, 33);
            updateClock();
            </script>
        """, height=180)
       
        if st.button("🔄 서버 시간 다시 가져오기"):
            st.session_state.ridi_server_time = get_ridibooks_server_time()
            st.session_state.ridi_time_counter = RidiTimeCounter(st.session_state.ridi_server_time)        

    with tabs[3]:
        render_rain_data_tab()


    with tabs[4]:
        ADMIN_PASSWORD = st.secrets["admin_token"]
        admin_input = st.text_input("⚜️ Admin", type="password")
        st.info("※ 관리자 전용입니다.")

        if admin_input:
            if admin_input == ADMIN_PASSWORD:
                st.success("⚜️ 관리자 인증 성공!")
            else:
                st.error("비밀번호가 틀렸습니다.")
                
if __name__ == "__main__":
    run_app()
