# -*- coding: utf-8 -*-
"""
수원유스호스텔 캠핑장 예약 페이지를 확인해서
지정한 날짜에 빈자리가 생기면 텔레그램으로 알려주는 스크립트.

이 사이트는 달력이 자바스크립트로 나중에 채워지는 방식이라
requests만으로는 안 되고, headless 브라우저(Playwright)로
실제 화면을 렌더링한 다음 텍스트를 읽어야 한다.

[1차 버전 안내]
아직 실제 달력이 어떤 모양(텍스트 구조)으로 나오는지 확인 전이라,
지금은 페이지에서 읽은 텍스트를 통째로 로그에 찍기만 한다.
이 로그를 보고 나서 "몇 일에 빈자리 있음"을 정확히 판정하는 로직을
다음 버전에서 다듬을 예정.
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL = (
    "https://yeyak.syf.or.kr/www/88"
    "?company_code=SYF09&part_code=02&place_code=2&days=1&date_yyyymm=202610"
)
TARGET_DAY = "4"  # 확인하고 싶은 날짜 (10월 4일)

STATE_FILE = "camp_state.json"


def send_telegram(text):
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def fetch_calendar_html():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="ko-KR")
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)  # 자바스크립트가 달력을 다 채울 시간을 여유있게 줌
        html = page.content()
        browser.close()
        return html


def main():
    state = load_state()

    try:
        html = fetch_calendar_html()
    except Exception as e:
        print("페이지를 불러오는 데 실패했습니다:", e)
        return

    soup = BeautifulSoup(html, "html.parser")

    # "예약완료"가 들어있는 테이블 = 달력 테이블일 가능성이 높음
    target_table = None
    for t in soup.find_all("table"):
        if "예약완료" in t.get_text():
            target_table = t
            break

    if target_table is None:
        print("달력 테이블을 찾지 못했습니다. 전체 테이블 개수:", len(soup.find_all("table")))
        return

    print("=== 달력 테이블 HTML (앞부분 6000자) ===")
    print(str(target_table)[:6000])
    print("=== 여기까지 ===")

    # 이번 실행은 정찰용이라 알림/상태 판정은 하지 않음
    save_state(state)


if __name__ == "__main__":
    main()
