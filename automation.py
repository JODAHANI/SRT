"""SRT 실제 사이트(etk.srail.kr) Playwright 자동화 모듈"""

import time
import re
import random
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from playwright_stealth import Stealth

# ── 텔레그램 알림 ─────────────────────────────────────────────
_TG_TOKEN   = "8788930387:AAE0D4SeQXaS7BMLWiVQTbk79SyhjB48B78"
_TG_CHAT_ID = "6467467226"

def _telegram(msg: str):
    try:
        url  = f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": _TG_CHAT_ID, "text": msg}).encode()
        urllib.request.urlopen(url, data=data, timeout=5)
    except Exception:
        pass

_stealth = Stealth(
    navigator_languages_override=("ko-KR", "ko"),
    navigator_platform_override="MacIntel",
    navigator_vendor_override="Google Inc.",
)

MEMBER_ID = "1594713026"
PASSWORD  = "zmzmzm123!"

LOGIN_URL = "https://etk.srail.kr/cmc/01/selectLoginForm.do"
MAIN_URL  = "https://etk.srail.kr/main.do"

STATION_CODES = {"수서": "0551", "부산": "0020"}
SEAT_CODE     = {"일반": "1",   "특실": "2"}

# 마우스 현재 위치 추적 (베지어 이동에 사용)
_mx, _my = 640.0, 400.0


def run(dep, arr, date, time_val, max_time_val, seat_type, auto_retry, adults, headless, status):
    psrm     = SEAT_CODE[seat_type]
    dep_code = STATION_CODES[dep]
    arr_code = STATION_CODES[arr]
    date_fmt = f"{date[:4]}.{date[4:6]}.{date[6:]}"

    attempts = 0   # 전체 시도 횟수 (세션 걸쳐 누적)

    with sync_playwright() as p:
        # ── 세션 루프: 12~15분마다 브라우저 재시작 → 새 WMONID ──────
        while status.get("status") == "running":
            session_start = time.time()
            SESSION_LIMIT = random.uniform(720, 900)   # 12~15분

            global _mx, _my
            _mx, _my = random.uniform(300, 900), random.uniform(400, 650)

            vw = random.choice([1366, 1440, 1536, 1920]) + random.randint(-4, 4)
            vh = random.choice([768,  800,  864,  900])  + random.randint(-4, 4)

            browser = p.chromium.launch(
                headless=headless,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                viewport={"width": vw, "height": vh},
                locale="ko-KR",
                timezone_id="Asia/Seoul",
            )
            page = context.new_page()
            _stealth.apply_stealth_sync(page)
            # JS alert("잔여석이 없습니다") 자동 dismiss
            page.on("dialog", lambda d: d.accept())

            try:
                # ── 1. 로그인 ──────────────────────────────────────
                status["message"] = "SRT 로그인 중..."
                page.goto(LOGIN_URL, wait_until="load")
                _natural_wait(page, 2.0, 3.5)

                # Escape로 열린 메뉴 닫고, 헤더 드롭다운이 완전히 닫힐 때까지 대기
                page.keyboard.press("Escape")
                _rand_sleep(0.5, 0.9)
                _vp0 = page.viewport_size or {"width": 1280, "height": 900}
                _bezier_move(page, _vp0["width"] / 2, _vp0["height"] * 0.55)
                _rand_sleep(0.5, 0.8)

                _human_type(page, "#srchDvNm01", MEMBER_ID)
                _rand_sleep(0.5, 1.1)
                _human_type(page, "#hmpgPwdCphd01", PASSWORD)
                _rand_sleep(0.8, 1.5)
                # 로그인 버튼 클릭 전: 마우스를 nav에서 완전히 벗어난 위치로 이동 후
                # hover 드롭다운이 닫힐 때까지 충분히 대기
                vp = page.viewport_size or {"width": 1280, "height": 900}
                page.mouse.move(vp["width"] / 2, vp["height"] * 0.7)
                _rand_sleep(0.6, 1.0)   # CSS hover 효과 꺼질 때까지 대기
                page.keyboard.press("Escape")
                _rand_sleep(0.2, 0.4)
                _loc_submit = page.locator(".loginSubmit").first
                try:
                    _loc_submit.click(timeout=5000)
                except Exception:
                    _loc_submit.click(force=True)
                try:
                    page.wait_for_load_state("load", timeout=20000)
                except PWTimeout:
                    pass

                if "selectLoginForm" in page.url:
                    err = page.inner_text(".err_msg, .error, .alert") or "아이디/비밀번호 확인"
                    status.update({"status": "error", "message": f"로그인 실패: {err}"})
                    return

                # ── 2. 메인 페이지 조건 설정 ───────────────────────
                status["message"] = "로그인 완료 — 메인 페이지 이동"
                page.goto(MAIN_URL, wait_until="load")
                _natural_wait(page, 2.5, 4.0)

                page.select_option("#dptRsStnCd", value=dep_code)
                _rand_sleep(0.5, 1.0)
                page.select_option("#arvRsStnCd", value=arr_code)
                _rand_sleep(0.5, 1.1)
                page.evaluate(f"""() => {{
                    const el = document.getElementById('cal');
                    el.value = '{date_fmt}';
                    el.dispatchEvent(new Event('input',  {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}""")
                _rand_sleep(0.5, 0.9)
                page.select_option("#dptTm", value=time_val)
                _rand_sleep(0.5, 1.0)

                if adults != 1:
                    _bezier_click(page, "#passenger")
                    page.wait_for_selector("#passengerAreaLayer", state="visible", timeout=3000)
                    for _ in range(adults - 1):
                        _bezier_click(page, "#psg1PlusBtn")
                        _rand_sleep(0.4, 0.8)
                    _bezier_click(page, "#passengerOkBtn")
                    page.wait_for_selector("#passengerAreaLayer", state="hidden", timeout=3000)
                    _rand_sleep(0.5, 0.9)

                status["message"] = "열차 조회 중..."
                _rand_sleep(0.8, 1.5)
                _bezier_click(page, "button[onclick*='selectScheduleList']")
                try:
                    page.wait_for_load_state("load", timeout=30000)
                except PWTimeout:
                    pass

                _wait_queue(page, status)
                if status.get("status") != "running":
                    return
                _wait_cover_spin(page)

                # ── 3. 예매 반복 루프 ──────────────────────────────
                # 검색 클릭 시각을 기록해서 최소 간격만 보장
                # (페이지 로드가 이미 오래 걸렸으면 추가 대기 없음)
                MIN_GAP = random.uniform(4, 8)   # SRT가 허용하는 최소 재조회 간격
                last_search_t = time.time()       # 첫 조회 클릭 시각

                while status.get("status") == "running":
                    attempts += 1
                    status["attempts"] = attempts

                    if _is_blocked(page):
                        status["message"] = f"차단 감지 — 세션 재시작 ({attempts}회)"
                        break

                    session_age = time.time() - session_start
                    if session_age >= SESSION_LIMIT:
                        status["message"] = f"세션 갱신 중... ({attempts}회)"
                        break

                    # 현재 페이지부터 '다음' 페이지까지 순차 탐색
                    found = False
                    diag  = ""
                    while status.get("status") == "running":
                        status["message"] = f"예매 버튼 탐색 중... ({attempts}회)"
                        found, diag, last_dep = _find_and_click_reserve_btn(
                            page, psrm, max_time_val or ""
                        )
                        if found:
                            break

                        # 마지막 열차 시각 < max_time → 다음 페이지에 더 있을 수 있음
                        if max_time_val and last_dep and last_dep < max_time_val:
                            status["message"] = f"다음 시간대 확인 중... ({attempts}회)"
                            if _click_next_page(page):
                                _rand_sleep(0.5, 1.0)
                                _wait_cover_spin(page)
                                continue   # 다음 페이지 탐색

                        break  # 더 볼 페이지 없음 → 재조회

                    if found:
                        msg = f"🎉 SRT 예매 성공!\n{dep}→{arr} {date_fmt} {time_val[:2]}시 이후\n결제 창 확인하세요!"
                        status["message"] = msg
                        status["status"] = "success"
                        _telegram(msg)
                        time.sleep(120)
                        return

                    if not auto_retry:
                        status.update({"status": "error", "message": f"매진 — {diag}"})
                        return

                    # 최소 간격 대기
                    elapsed = time.time() - last_search_t
                    gap_remain = max(0.0, MIN_GAP - elapsed)
                    for i in range(int(gap_remain), 0, -1):
                        if status.get("status") != "running":
                            return
                        status["message"] = f"매진 ({attempts}회) [{diag}] — {i}초 후 재조회"
                        time.sleep(1)

                    MIN_GAP = random.uniform(4, 8)
                    last_search_t = time.time()
                    # max_time 설정 시 시간 필터를 시작 시각으로 리셋 후 재조회
                    if max_time_val:
                        _reset_time_and_search(page, time_val)
                    else:
                        _click_search_on_results(page)
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=20000)
                    except PWTimeout:
                        pass

                    _wait_queue(page, status)
                    if status.get("status") != "running":
                        return
                    _wait_cover_spin(page)

            except Exception as e:
                status["message"] = f"세션 오류: {e} — 재시작"
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

            if status.get("status") != "running":
                return

            # 세션 재시작 전 대기 (새 WMONID 발급 간격)
            restart_wait = random.randint(8, 15)
            for i in range(restart_wait, 0, -1):
                if status.get("status") != "running":
                    return
                status["message"] = f"세션 재시작 대기 ({i}초)..."
                time.sleep(1)


# ── 헬퍼 함수들 ────────────────────────────────────────────────────────────────

def _is_blocked(page) -> bool:
    """차단/접속제한 페이지 감지"""
    try:
        text = page.inner_text("body")
        return any(kw in text for kw in ("접속 제한", "비정상적인 요청", "차단되었습니다", "이용제한"))
    except Exception:
        return False


def _rand_sleep(lo: float = 0.3, hi: float = 0.9):
    time.sleep(random.uniform(lo, hi))


def _natural_wait(page, lo: float = 2.0, hi: float = 4.0):
    """페이지 로드 후 사람처럼 대기 — 마우스 이동 + 스크롤 포함.
    봇 감지 JS가 WMONID 등 초기 쿠키를 세팅하기까지 충분히 기다림."""
    try:
        vp = page.viewport_size or {"width": 1280, "height": 900}
        vw, vh = vp["width"], vp["height"]

        total = random.uniform(lo, hi)
        elapsed = 0.0

        # 마우스를 2~3번 자연스럽게 이동
        # y=400 이상 → nav + 드롭다운 영역(~350px) 완전 회피
        for _ in range(random.randint(1, 3)):
            tx = random.uniform(80, vw - 80)
            ty = random.uniform(400, vh - 80)
            _bezier_move(page, tx, ty)
            t = random.uniform(0.3, 0.7)
            time.sleep(t)
            elapsed += t
            if elapsed >= total:
                return

        # 짧은 스크롤
        _scroll_briefly(page)
        elapsed += 0.8

        # 남은 시간 순수 대기
        remaining = total - elapsed
        if remaining > 0:
            time.sleep(remaining)
    except Exception:
        time.sleep(random.uniform(lo, hi))


def _scroll_briefly(page):
    """사람처럼 페이지 조금 스크롤 후 돌아옴"""
    try:
        dist = random.randint(80, 250)
        page.mouse.wheel(0, dist)
        _rand_sleep(0.3, 0.7)
        page.mouse.wheel(0, -dist)
        _rand_sleep(0.2, 0.5)
    except Exception:
        pass


def _bezier_move(page, tx: float, ty: float):
    """현재 위치에서 (tx, ty)까지 베지어 곡선으로 마우스 이동"""
    global _mx, _my
    sx, sy = _mx, _my
    dist = ((tx - sx) ** 2 + (ty - sy) ** 2) ** 0.5
    steps = max(12, int(dist / 15))

    # 제어점 굴곡 — y축은 위로 튀지 않도록 클램프 (nav + 드롭다운 방지)
    cx = (sx + tx) / 2 + random.uniform(-40, 40)
    cy = max(380.0, (sy + ty) / 2 + random.uniform(-30, 30))

    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t ** 2 * tx
        y = (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t ** 2 * ty
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.004, 0.014))

    _mx, _my = tx, ty


def _bezier_click(page, selector: str):
    """베지어 곡선 이동 후 클릭. Locator 기반 → stale 없음."""
    loc = page.locator(selector).first
    try:
        loc.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass

    box = None
    try:
        box = loc.bounding_box()
    except Exception:
        pass

    if box:
        tx = box["x"] + box["width"]  * random.uniform(0.3, 0.7)
        ty = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        _bezier_move(page, tx, ty)
        _rand_sleep(0.08, 0.22)

    try:
        loc.click(timeout=6000)
    except Exception:
        loc.click(force=True)


def _human_type(page, selector: str, text: str):
    """한 글자씩 랜덤 딜레이로 타이핑."""
    loc = page.locator(selector).first
    try:
        loc.click(timeout=3000)
    except Exception:
        try:
            # 헤더/드롭다운이 가로막는 경우 force=True로 우회
            loc.click(force=True)
        except Exception:
            # 최후 수단: JS focus (오버레이 완전 무시)
            page.evaluate(f"document.querySelector('{selector}').focus()")
    page.fill(selector, "")
    for ch in text:
        page.type(selector, ch, delay=random.randint(55, 190))


def _click_search_on_results(page):
    """결과 페이지 조회하기 버튼 — 여러 셀렉터 순서대로 시도"""
    for sel in [
        "input.inquery_btn",
        "input[value='조회하기']",
        "button[onclick*='selectScheduleList']",
        "#search-form input[type='submit']",
    ]:
        loc = page.locator(sel).first
        if loc.count() == 0:
            continue
        try:
            loc.scroll_into_view_if_needed(timeout=3000)
            _rand_sleep(0.15, 0.35)
            box = loc.bounding_box()
            if box:
                tx = box["x"] + box["width"]  * random.uniform(0.3, 0.7)
                ty = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                _bezier_move(page, tx, ty)
                _rand_sleep(0.08, 0.2)
            loc.click(timeout=6000)
            return
        except Exception:
            try:
                loc.click(force=True)
                return
            except Exception:
                continue
    # 최후 수단: 폼 submit 이벤트 발생 (form.submit() 보다 덜 수상)
    page.evaluate("""() => {
        const form = document.getElementById('search-form')
                  || document.querySelector('form[name="search-form"]');
        if (form) form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
    }""")


def _wait_cover_spin(page):
    try:
        page.wait_for_selector("#cover-spin", state="visible", timeout=3000)
    except PWTimeout:
        pass
    try:
        page.wait_for_selector("#cover-spin", state="hidden", timeout=30000)
    except PWTimeout:
        pass


def _wait_queue(page, status, poll_sec: int = 3, max_wait: int = 1800):
    _QUEUE_KEYWORDS = ("접속 대기", "대기번호", "잠시 후 접속")
    deadline = time.time() + max_wait

    while time.time() < deadline:
        if status.get("status") != "running":
            return
        try:
            body_text = page.inner_text("body")
        except Exception:
            return
        if not any(kw in body_text for kw in _QUEUE_KEYWORDS):
            return

        hint_parts = []
        m_num  = re.search(r"대기\s*번호[^\d]*(\d+)", body_text)
        m_time = re.search(r"예상\s*(?:대기\s*)?시간[^\d]*(\d+)\s*(?:분|초)", body_text)
        m_cnt  = re.search(r"(\d+)\s*명", body_text)
        if m_num:  hint_parts.append(f"대기번호 {m_num.group(1)}")
        if m_time: hint_parts.append(f"예상 {m_time.group(1)}{body_text[m_time.end()-1]}")
        if m_cnt and not m_num: hint_parts.append(f"{m_cnt.group(1)}명 대기 중")

        hint = f" ({', '.join(hint_parts)})" if hint_parts else ""
        status["message"] = f"접속 대기 중...{hint}"
        try:
            page.wait_for_load_state("domcontentloaded", timeout=poll_sec * 1000)
        except PWTimeout:
            pass

    status.update({"status": "error", "message": "접속 대기 시간 초과 (30분)"})


def _click_next_page(page) -> bool:
    """결과 목록 하단 '다음' 버튼 클릭. 성공 시 True 반환."""
    selectors = [
        "a.btn_next_arrow",
        "a.next_btn",
        ".paging a.next",
        ".pagination a.next",
        "a[onclick*='next']",
        "button[onclick*='next']",
        "input[value='다음']",
        ".paging a:has-text('다음')",
        ".btn_wrap a:has-text('다음')",
        "a:has-text('다음')",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            cls = (loc.get_attribute("class") or "").lower()
            if any(kw in cls for kw in ("disabled", "inactive", "dim")):
                continue
            loc.scroll_into_view_if_needed(timeout=3000)
            _rand_sleep(0.15, 0.35)
            loc.click(timeout=5000)
            return True
        except Exception:
            try:
                page.locator(sel).first.click(force=True)
                return True
            except Exception:
                continue
    return False


def _reset_time_and_search(page, time_val: str):
    """결과 페이지 상단 출발 시각을 time_val로 초기화 후 조회하기 클릭."""
    try:
        page.select_option("#dptTm", value=time_val)
        _rand_sleep(0.3, 0.6)
    except Exception:
        try:
            page.select_option("select[name='dptTm']", value=time_val)
            _rand_sleep(0.3, 0.6)
        except Exception:
            pass
    _click_search_on_results(page)


def _find_and_click_reserve_btn(page, psrm_cl_cd: str, max_time_val: str) -> tuple[bool, str, str]:
    """
    열 위치 기반으로 예매 버튼 탐지 (스크린샷 기준):
      특실 = 6번째 td, 일반실 = 7번째 td
    클릭 우선순위: 예약하기 > 입석+좌석 > 좌석선택
    반환: (성공여부, 진단메시지, 이_페이지_마지막_열차_출발시각_HHMMSS)
    """
    col_nth   = 7 if psrm_cl_cd == "1" else 6
    seat_name = "일반실" if psrm_cl_cd == "1" else "특실"

    # 열차 행이 로딩될 때까지 대기
    try:
        page.wait_for_selector("tbody tr td, tr td:nth-child(6)", timeout=3000)
    except PWTimeout:
        pass

    # 데이터 행 수집 (thead 제외 — td 3개 이상인 tr)
    rows = page.locator(f"tr:has(td:nth-child({col_nth}))")
    total = rows.count()

    if total == 0:
        return False, f"열차 행 0개 — 페이지 로딩 중이거나 결과 없음", ""

    skipped_sold = 0
    skipped_time = 0
    tried = 0
    last_row_dep = ""   # 이 페이지의 마지막 열차 출발 시각 (다음 페이지 여부 판단용)

    for i in range(total):
        row = rows.nth(i)

        # 출발 시각 추출 — 필터 여부와 무관하게 항상 추적
        row_dep = ""
        try:
            row_text = row.inner_text()
            m = re.search(r'(\d{2}):(\d{2})', row_text)
            if m:
                row_dep = m.group(1) + m.group(2) + "00"
                last_row_dep = row_dep
        except Exception:
            pass

        # 시간 필터
        if max_time_val and row_dep and row_dep >= max_time_val:
            skipped_time += 1
            continue

        # 해당 열 (특실 or 일반실) TD
        td = row.locator(f"td:nth-child({col_nth})").first
        if td.count() == 0:
            continue

        try:
            td_text = td.inner_text().strip()
        except Exception:
            continue

        # 매진만 있는 셀은 스킵
        if not td_text or (td_text == "매진"):
            skipped_sold += 1
            continue

        # 클릭할 버튼 우선순위 탐색
        tried += 1
        row_done = False
        for label in ["예약하기", "입석+좌석", "좌석선택"]:
            if row_done:
                break
            btn = td.locator(f"a:has-text('{label}'), input[value='{label}']").first
            if btn.count() == 0:
                continue
            try:
                if btn.get_attribute("disabled") is not None:
                    continue

                before_url = page.url
                btn.click()

                # URL 변화 대기
                try:
                    page.wait_for_url(lambda url: url != before_url, timeout=5000)
                except PWTimeout:
                    # URL 그대로 = alert dismiss됐거나 클릭 무반응 → 다음 라벨
                    continue

                # URL 바뀜 → 페이지 로딩 후 내용 확인
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass

                try:
                    body = page.inner_text("body")
                except Exception:
                    body = ""

                _FAIL_KEYWORDS = ("잔여석없음", "잔여석이 없습니다", "잔여석 없음", "좌석이 없습니다")
                if any(kw in body for kw in _FAIL_KEYWORDS):
                    # 잔여석없음 페이지 → 확인 눌러서 돌아가기
                    try:
                        confirm = page.locator("a:has-text('확인'), button:has-text('확인')").first
                        if confirm.count() > 0:
                            confirm.click()
                            page.wait_for_load_state("domcontentloaded", timeout=10000)
                        else:
                            page.go_back()
                            page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        pass
                    row_done = True   # 이 행은 포기, 다음 열차로
                    break

                # 잔여석없음 없음 = 진짜 예매 페이지 진입
                return True, f"'{label}' 예매 성공 (행{i+1})", last_row_dep

            except Exception:
                continue

    diag = (
        f"{seat_name} | 전체{total}행 | "
        f"매진{skipped_sold} 시간초과{skipped_time} 탐색{tried}행"
    )
    return False, diag, last_row_dep

    return False
