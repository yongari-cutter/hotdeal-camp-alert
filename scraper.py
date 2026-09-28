# -*- coding: utf-8 -*-
"""
FM코리아 핫딜 게시판을 주기적으로 확인해서
등록한 키워드가 제목에 포함된 새 글이 올라오면 텔레그램으로 알려주는 스크립트.

동작 방식:
1. 핫딜 게시판 목록 페이지를 가져온다.
2. 글 번호(post_id)를 기준으로 "이미 본 글"인지 확인한다 (seen_ids.json).
3. 새 글 중 제목에 키워드가 들어간 글만 텔레그램으로 전송한다.
4. 처음 실행할 때는 스팸 방지를 위해 알림을 보내지 않고, 현재 있는 글들을 전부
   "이미 본 글"로만 기록해둔다. (그다음 실행부터 진짜 새 글만 알림이 온다)
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ── 설정 ────────────────────────────────────────────────
BOARD_URL = "https://www.fmkorea.com/hotdeal"

# 감지하고 싶은 키워드. 제목에 이 중 하나라도 포함되면 알림이 옵니다.
KEYWORDS = [
    "키보드",
    "모니터",
    "모달",
    "마우스",
    "컬쳐랜드",
    "컬처랜드",
    "북앤라이프",
    "문화상품권",
    "상품권",
]

STATE_FILE = "seen_ids.json"

# 글 링크 패턴: https://www.fmkorea.com/1234567890 또는 /1234567890 형태
POST_LINK_RE = re.compile(r"^(?:https?://www\.fmkorea\.com)?/?(\d{6,})(?:\?.*)?$")


def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()


def save_seen(seen_ids):
    # 파일이 무한정 커지지 않도록 최근 1000개만 유지
    trimmed = list(seen_ids)[-1000:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False)


def send_telegram(text):
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=10,
    )
    if resp.status_code != 200:
        print("텔레그램 전송 실패:", resp.status_code, resp.text)


def fetch_posts():
    """핫딜 게시판에서 (글번호, 제목, 링크) 목록을 뽑아온다.

    requests 라이브러리로는 계속 430(차단)이 나서,
    진짜 크롬 브라우저(Playwright)로 접속해서 가져오는 방식으로 바꿈.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="ko-KR")
        page.goto(BOARD_URL, wait_until="networkidle", timeout=30000)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")

    posts = []
    seen_on_page = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        m = POST_LINK_RE.match(href)
        if not m:
            continue

        post_id = m.group(1)
        title = a.get_text(strip=True)

        # 제목 없는 링크(썸네일 이미지 링크 등)는 건너뜀
        if not title or len(title) < 2:
            continue
        if post_id in seen_on_page:
            continue

        seen_on_page.add(post_id)
        posts.append((post_id, title, f"https://www.fmkorea.com/{post_id}"))

    return posts


def main():
    first_run = not os.path.exists(STATE_FILE)
    seen = load_seen()

    if not os.path.exists(STATE_FILE):
        # git add가 실패하지 않도록 파일을 먼저 만들어둔다
        save_seen(seen)

    try:
        posts = fetch_posts()
    except Exception as e:
        print("게시판을 불러오는 데 실패했습니다:", e)
        return

    new_seen = set(seen)
    matched = []

    for post_id, title, url in posts:
        if post_id in seen:
            continue
        new_seen.add(post_id)

        if first_run:
            # 첫 실행에서는 알림을 보내지 않고 기록만 함 (스팸 방지)
            continue

        for kw in KEYWORDS:
            if kw in title:
                matched.append((title, url, kw))
                break

    if first_run:
        print(f"초기 실행: 현재 글 {len(new_seen)}개를 기록했습니다. "
              f"다음 실행부터 새 글에 대해 알림이 갑니다.")
    else:
        print(f"이번 확인에서 새 글 {len(posts) - len(seen & {p[0] for p in posts})}개 중 "
              f"키워드 매칭 {len(matched)}개 발견")

    for title, url, kw in matched:
        send_telegram(f"🔥 [{kw}] {title}\n{url}")

    save_seen(new_seen)


if __name__ == "__main__":
    main()
