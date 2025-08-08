import requests
import pandas as pd
from io import StringIO
from datetime import date, timedelta
import streamlit as st
from config import Config

COL_NAMES = [
    "YYMMDDHHMI", "STN", "WD1", "WS1", "WDS", "WSS",
    "WD10", "WS10", "TA", "RE", "RN-15m", "RN-60m",
    "RN-12H", "RN-DAY", "HM", "PA", "PS", "TD"
]

def make_api_url(date_obj: date, auth_key: str, time_start: str, time_end: str, stn=Config.STATION_CODE) -> str:
    ymd = date_obj.strftime('%Y%m%d')
    return f"https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-aws2_min?tm1={ymd}{time_start}&tm2={ymd}{time_end}&stn={stn}&disp=0&help=0&authKey={auth_key}"

def is_cache_applicable(date_obj: date, today=None) -> bool:
    if today is None:
        today = date.today()
    return (today - timedelta(days=31)) <= date_obj < today

@st.cache_data(show_spinner=False, ttl=21600)
def fetch_rain_data_cached(date_obj: date, auth_key: str, time_start="1000", time_end="1600"):
    df = fetch_rain_data_raw(date_obj, auth_key, time_start, time_end)
    if df is None:
        # 실패 시 캐시에 저장하지 않도록 예외 발생
        raise ValueError(f"API 실패로 캐시 저장 안 함: {date_obj}")
    return df

def fetch_rain_data(date_obj: date, auth_key: str, time_start="1000", time_end="1600"):
    today = date.today()
    try:
        if is_cache_applicable(date_obj, today):
            return fetch_rain_data_cached(date_obj, auth_key, time_start, time_end)
        else:
            return fetch_rain_data_raw(date_obj, auth_key, time_start, time_end)
    except Exception as e:
        # 캐시 실패 예외 발생 시 캐시 무시하고 재시도
        st.warning(f"{date_obj} 캐시 오류 발생: {e}. 캐시 무시 후 재시도합니다.")
        return fetch_rain_data_raw(date_obj, auth_key, time_start, time_end)

def fetch_rain_data_raw(date_obj: date, auth_key: str, time_start="1000", time_end="1600"):
    url = make_api_url(date_obj, auth_key, time_start, time_end)
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text), sep=r'\s+', comment='#', header=None, names=COL_NAMES, dtype=str, encoding='euc-kr')
        df['RE'] = pd.to_numeric(df['RE'], errors='coerce').fillna(0)
        return df
    except requests.exceptions.Timeout:
        st.error(f"{date_obj} - API 요청 타임아웃 발생")
    except Exception as e:
        st.error(f"{date_obj} - API 요청 실패: {e}")
    return None
