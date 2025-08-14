from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import holidays
from api import fetch_rain_data
from config import Config
import pytz
import streamlit as st

def is_business_day(d: date, kr_holidays) -> bool:
    return d.weekday() < 5 and d not in kr_holidays and not (d.month == 5 and d.day == 1)

def get_seoul_today() -> date:
    return datetime.now(pytz.timezone("Asia/Seoul")).date()

def get_time_range_for_today(date_obj: date) -> tuple[str, str]:
    now = datetime.now(pytz.timezone("Asia/Seoul")).time()
    seoul_today = get_seoul_today()

    if date_obj != seoul_today:
        return Config.TIME_START, Config.TIME_END
    if now < Config.TIME_START_OBJ:
        return Config.TIME_START, Config.TIME_START
    elif now >= Config.TIME_END_OBJ:
        return Config.TIME_START, Config.TIME_END
    return Config.TIME_START, (datetime.now(pytz.timezone("Asia/Seoul")) - timedelta(minutes=1)).strftime("%H%M")

def daterange(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)

def check_bipo_status(date_obj: date, df: pd.DataFrame, kr_holidays, time_end: str) -> tuple[str, tuple[str, ...]]:
    if not is_business_day(date_obj, kr_holidays):
        return "pass", tuple()

    if df is None or 'RE' not in df.columns:
        return "fail", tuple()

    df = df.copy()
    df['HHMM'] = df['YYMMDDHHMI'].str[-4:]
    df['RE'] = pd.to_numeric(df['RE'], errors='coerce').fillna(0)

    mask = (df['HHMM'] >= Config.TIME_START) & (df['HHMM'] <= time_end) & (df['RE'] != 0)
    rain_times = df.loc[mask, 'HHMM'].tolist()
    rain_times_formatted = [f"{t[:2]}:{t[2:]}" for t in rain_times]

    if rain_times_formatted:
        return "rain_detected", tuple(rain_times_formatted)
    return "no_rain", tuple()

def process_dates_with_threadpool(dates, auth_key, kr_holidays):
    results = []

    def worker(date_obj):
        try:
            t_start, t_end = get_time_range_for_today(date_obj)
            df = fetch_rain_data(date_obj, auth_key, t_start, t_end)
            status = check_bipo_status(date_obj, df, kr_holidays, t_end)
            return date_obj, status
        except Exception as e:
            return date_obj, ("fail", tuple())

    with ThreadPoolExecutor(max_workers=Config.MAX_THREADS) as executor:
        results = list(executor.map(worker, dates))

    result_by_status = {
        "rain_detected": [],
        "no_rain": [],
        "pass": [],
        "fail": [],
    }


    for d, status in results:
        result_by_status[status[0]].append(d)
        st.write(f"{d}: {status[0]}")

    return result_by_status
