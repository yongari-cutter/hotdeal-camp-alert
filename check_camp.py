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


def fetch_page_text():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="ko-KR")
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)  # 자바스크립트가 달력을 다 채울 시간을 여유있게 줌
        text = page.inner_text("body")
        browser.close()
        return text


def main():
    state = load_state()

    try:
        text = fetch_page_text()
    except Exception as e:
        print("페이지를 불러오는 데 실패했습니다:", e)
        return

    # ── 1차 버전: 실제 내용을 로그로 확인하기 위한 출력 ──────────
    print("=== 페이지에서 읽은 텍스트 (앞부분 3000자) ===")
    print(text[:3000])
    print("=== 여기까지 ===")

    # 아주 단순한 임시 판정 (다음 버전에서 정확하게 다듬을 예정)
    available = (TARGET_DAY in text) and ("예약완료" not in text)
    was_available = state.get("available", False)

    print(f"임시 판정 결과: available={available}")

    if available and not was_available:
        send_telegram(f"🏕️ {TARGET_DAY}일에 빈자리가 생겼을 수도 있어요! 확인해보세요:\n{URL}")

    state["available"] = available
    save_state(state)


if __name__ == "__main__":
    main()
