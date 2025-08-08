import requests
from datetime import date
import streamlit as st
from streamlit_js_eval import streamlit_js_eval
from api import make_api_url
from config import Config

def load_auth_key_once(retry=False) -> str | None:
    if "auth_key" not in st.session_state:
        key = streamlit_js_eval(
            js_expressions="localStorage.getItem('api_key')",
            key="get_api_key_retry" if retry else "get_api_key",  # key 다르게
            label="🔐 로컬스토리지에서 인증키 불러오는 중..."
        )
        if not key:
            return None
        st.session_state.auth_key = key
    return st.session_state.auth_key

def save_auth_key(key: str):
    streamlit_js_eval(
        js_expressions=f"localStorage.setItem('api_key', '{key}')",
        key="save_api_key",
        label="Save API key to localStorage"
    )

def test_auth_key(auth_key: str) -> bool:
    today = date.today()
    url = make_api_url(today, auth_key, Config.TIME_START, Config.TIME_START)
    try:
        r = requests.get(url, timeout=10)
        return r.status_code == 200 and "RE" in r.text
    except requests.RequestException as e:
        st.error(f"API 인증 중 오류 발생: {e}")
        return False

def is_admin() -> bool:
    admin_input = st.session_state.get("admin_token")
    admin_secret = st.secrets.get("admin_token")
    return bool(admin_input and admin_input == admin_secret)

def get_auth_key(retry: bool = False) -> tuple[str | None, bool]:
    if "auth_key" in st.session_state and "auth_ok" in st.session_state:
        return st.session_state.auth_key, st.session_state.auth_ok

    if is_admin():
        key = st.secrets["API_KEY"]
        st.session_state.auth_key = key
        st.session_state.auth_ok = True
        return key, True

    key = load_auth_key_once(retry=retry)  #  retry 값 전달
    ok = test_auth_key(key) if key else False

    if ok:
        st.session_state.auth_key = key
        st.session_state.auth_ok = True

    return key, ok
