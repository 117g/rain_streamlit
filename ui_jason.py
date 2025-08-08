import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from collections import defaultdict
import altair as alt

def load_rain_data():
    url = "https://raw.githubusercontent.com/117g/rain_streamlit/main/rainy_json_save_20200101-20250704.json"
    resp = requests.get(url)
    if resp.status_code == 200:
        return resp.json()
    else:
        st.error(f"데이터 불러오기 실패 (status_code={resp.status_code})")
        return None

def preprocess_data(rain_minutes_by_date):
    data = defaultdict(lambda: defaultdict(int))
    for date_str, minutes_list in rain_minutes_by_date.items():
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if minutes_list:
            data[dt.year][dt.month] += 1
    rows = []
    for year, months in data.items():
        for month, count in months.items():
            rows.append({"year": year, "month": month, "rain_count": count})
    df = pd.DataFrame(rows)
    return df

def compute_average(df, year_ranges):
    avg_dfs = []
    for label, years in year_ranges:
        sub_df = df[df['year'].isin(years)]
        avg_month = sub_df.groupby('month')['rain_count'].mean().reset_index()
        avg_month['period'] = label
        avg_month = avg_month.rename(columns={'rain_count': 'avg_rain_count'})
        avg_dfs.append(avg_month)
    avg_df = pd.concat(avg_dfs, ignore_index=True)
    return avg_df

def render_rain_data_tab():
    st.title("💧 Rain Data Analysis")

    rain_data = load_rain_data()
    if rain_data is None:
        return

    rain_minutes_by_date = rain_data.get("rain_minutes_by_date", {})
    df = preprocess_data(rain_minutes_by_date)

    st.header("1. 기간별 평균 비 횟수 비교")

    latest_year = df['year'].max()
    periods = {
        "최근 5년": list(range(latest_year-4, latest_year+1)),
        "최근 3년": list(range(latest_year-2, latest_year+1)),
        "최근 1년": [latest_year]
    }

    selected_periods = st.multiselect("기간 선택", options=list(periods.keys()), default=list(periods.keys()))

    cols = st.columns(len(periods))
    for i, (label, years) in enumerate(periods.items()):
        sub_df = df[df['year'].isin(years)]
        if not sub_df.empty:
            min_year, min_month = sub_df.loc[sub_df['month'].idxmin()][['year', 'month']]
            max_year, max_month = sub_df.loc[sub_df['month'].idxmax()][['year', 'month']]
            cols[i].write(f"**{label} 기간:** {min_year}-{min_month:02d} ~ {max_year}-{max_month:02d}")

    if not selected_periods:
        st.warning("최소 한 개 이상의 기간을 선택해주세요.")
    else:
        year_ranges = [(label, periods[label]) for label in selected_periods]
        avg_df = compute_average(df, year_ranges)

        area_chart = alt.Chart(avg_df).mark_area(opacity=0.4).encode(
            x=alt.X('month:O', title='월'),
            y=alt.Y('avg_rain_count:Q', title='평균 비 횟수', stack=None),
            color=alt.Color('period:N', legend=alt.Legend(title="기간", orient='bottom')),
            tooltip=['period', 'month', 'avg_rain_count']
        ).properties(width=700, height=400).interactive()

        st.altair_chart(area_chart, use_container_width=True)

    st.header("2. 연도별 월별 비 횟수 비교 (Line Chart)")

    years = sorted(df['year'].unique())
    selected_years = st.multiselect("연도 선택", options=years, default=years)

    if not selected_years:
        st.warning("최소 한 개 이상의 연도를 선택해주세요.")
    else:
        line_df = df[df['year'].isin(selected_years)]

        line_chart = alt.Chart(line_df).mark_line(point=True).encode(
            x=alt.X('month:O', title='월'),
            y=alt.Y('rain_count:Q', title='비 횟수'),
            color=alt.Color('year:N', legend=alt.Legend(title="연도", orient='bottom')),
            tooltip=['year', 'month', 'rain_count']
        ).properties(width=700, height=400).interactive()

        st.altair_chart(line_chart, use_container_width=True)

# 아래는 Streamlit 탭 안에서 호출 예시
def main():
    tabs = st.tabs(["기타 탭1", "기타 탭2", "기타 탭3", "Rain Data"])
    with tabs[3]:
        render_rain_data_tab()

if __name__ == "__main__":
    main()
