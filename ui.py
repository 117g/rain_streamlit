import streamlit as st
import calendar
from datetime import date, timedelta, datetime
import streamlit.components.v1 as components
from time_ridibooks import get_ridibooks_server_time, RidiTimeCounter


def generate_rainy_calendar_html(start_date, end_date, status_by_dates):
    def generate_months(start, end):
        y, m = start.year, start.month
        while (y < end.year) or (y == end.year and m <= end.month):
            yield (y, m)
            m += 1
            if m == 13:
                m = 1
                y += 1

    def build_css():
        return """
        @font-face {
            font-family: 'Pretendard-Regular';
            src: url('https://cdn.jsdelivr.net/gh/Project-Noonnu/noonfonts_2107@1.1/Pretendard-Regular.woff') format('woff');
        }
        html, body {
            font-family: 'Pretendard-Regular', sans-serif;
            margin: 0;
            padding: 0;
            width: 100%;
            height: auto;
            overflow-x: hidden;
            background-color: transparent;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .calendar-wrapper {
            width: 95%;
            margin: 20px auto;
            padding: 10px;
            background-color: white;
            border-radius: 10px;
            text-align: center;
            box-sizing: border-box;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        .month-title { font-size:1.1em; font-weight:bold; color:steelblue; margin-bottom:10px; }
        .message { font-size:1em; color:steelblue; margin-bottom:10px; }
        .rain-count { margin-bottom:15px; font-size:0.95em; color:#666; }
        table { border-collapse: collapse; margin: 0 auto; width: 100%; table-layout: auto; }
        th, td { border: none; padding: 5px; text-align: center; }
        .rainy { color:steelblue; font-weight:bold; background-color:rgba(176,224,230,0.3); border-radius:4px; }
        .today { color:tomato; font-weight:bold; background-color:rgba(255,99,71,0.1); border-radius:4px; }
        .today-rain { color:green; font-weight:bold; background-color: rgba(23, 255, 87, 0.21); border-radius:4px; }
        .fail { color:white; background-color:gray; font-weight:bold; border-radius:4px; }
        .past, .future, .outside { color:lightgray; }
        ul.rainy-list { text-align:left; margin:0 0 10px 20px; padding-left:0; color:gray; font-size:0.9em; list-style-position:inside; }
        ul.rainy-list li { margin: 0 0 5px 20px; color: gray; font-size:0.85em; list-style-type:disc; }
        .rainy-list-header { text-align:left; margin:10px 0 4px 10px; font-weight:bold; color:steelblue; }
        """

    def generate_status_map(status_data, year, month):
        return {
            d: status for status, dates in status_data.items()
            for d in dates if d.year == year and d.month == month
        }

    def generate_counts(status_data, year, month):
        return {
            status: sum(1 for d in dates if d.year == year and d.month == month)
            for status, dates in status_data.items()
        }

    def format_day_cell(date_obj, today, status, start, end):
        classes = []
        if date_obj == today:
            if status == "rain_detected":
                classes.append("today-rain")
            elif status == "fail":
                classes.append("fail")
            else:
                classes.append("today")
        elif date_obj < start:
            classes.append("past")
        elif date_obj > end or status == "pass":
            classes.append("outside")
        elif status == "rain_detected":
            classes.append("rainy")
        elif status == "fail":
            classes.append("fail")
        return f'<td class="{" ".join(classes)}">{date_obj.day}</td>' if classes else f"<td>{date_obj.day}</td>"

    html_parts = [
        "<html><head>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        f"<style>{build_css()}</style></head><body>"
    ]

    weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    today = datetime.today().date()

    for year, month in generate_months(start_date, end_date):
        html_parts.append("<div class='calendar-wrapper'>")
        html_parts.append(f"<div class='month-title'>{month}월</div>")

        status_map = generate_status_map(status_by_dates, year, month)
        counts = generate_counts(status_by_dates, year, month)
        current_month = (today.year == year and today.month == month)

        #  메시지 영역
        if current_month:
            msg_map = {
                "rain_detected": "💧 오늘은 비포 받는 날!",
                "no_rain": "😞 현재 기준 비포가 없습니다.",
                "pass": "📅 오늘은 비포 대상일이 아닙니다.",
                "fail": "⚠️ 비포 여부를 확인할 수 없습니다. (API 오류 등)"
            }
            msg = msg_map.get(status_map.get(today), "오늘 정보가 없습니다.")
            html_parts.append(f"<div class='message'>{msg}</div>")
            html_parts.append(f"<div class='message rain-count'>💧 이번 달 비포 횟수: {counts.get('rain_detected', 0)}회</div>")
        else:
            html_parts.append(f"<div class='message rain-count'>💧 {month}월 비포 횟수: {counts.get('rain_detected', 0)}회</div>")

        #  캘린더 테이블
        html_parts.append("<table><tr>" + "".join(f"<th>{wd}</th>" for wd in weekdays) + "</tr>")
        for week in calendar.monthcalendar(year, month):
            html_parts.append("<tr>")
            for day in week:
                if day == 0:
                    html_parts.append("<td class='outside'>&nbsp;</td>")
                else:
                    d = date(year, month, day)
                    status = status_map.get(d)
                    html_parts.append(format_day_cell(d, today, status, start_date, end_date))
            html_parts.append("</tr>")
        html_parts.append("</table>")

        # 비포 리스트
        html_parts.append("<div class='rainy-list-header'>[비 온 날 리스트]</div><ul class='rainy-list'>")
        rainy_days = [d.strftime('%Y-%m-%d') for d in status_by_dates.get("rain_detected", []) if d.year == year and d.month == month]
        if rainy_days:
            html_parts.extend(f"<li>{r}</li>" for r in rainy_days)
        else:
            html_parts.append("<li>비 온 날 없음</li>")
        html_parts.append("</ul></div>")

    html_parts.append("</body></html>")
    return "\n".join(html_parts)


#  예시 데이터
status_by_dates = {
    "rain_detected": [date.today() - timedelta(days=3), date.today()],
    "no_rain": [],
    "pass": [],
    "fail": []
}

#  HTML 렌더링
html_code = generate_rainy_calendar_html(date.today() - timedelta(days=30), date.today(), status_by_dates)

st.components.v1.html(
    html_code,
    width=900,
    height=800,
    scrolling=True
)
