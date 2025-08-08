import requests
from datetime import datetime, timedelta, timezone
import time

def get_ridibooks_server_time():
    url = "https://ridibooks.com"
    try:
        start = time.time()
        response = requests.head(url, timeout=5)
        end = time.time()

        if 'Date' not in response.headers:
            raise ValueError("Date 헤더가 없습니다.")

        server_date_str = response.headers['Date']
        server_datetime = datetime.strptime(server_date_str, "%a, %d %b %Y %H:%M:%S GMT")
        server_datetime = server_datetime.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=9)))

        rtt = (end - start) * 1000
        estimated_time = server_datetime + timedelta(milliseconds=-(rtt / 2))

        return estimated_time

    except Exception as e:
        raise RuntimeError(f"서버 시간 조회 실패: {e}")

class RidiTimeCounter:
    def __init__(self, initial_server_time: datetime):
        self.initial_time = initial_server_time
        self.perf_start = time.perf_counter()

    def now(self) -> datetime:
        elapsed = time.perf_counter() - self.perf_start
        return self.initial_time + timedelta(seconds=elapsed)
