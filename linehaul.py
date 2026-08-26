import os
import re
import time
import traceback
from datetime import datetime, timedelta, timezone
import requests
from playwright.sync_api import sync_playwright

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
sheet_url = os.getenv("SHEET_URL")

# Khung giờ: From 0 hrs ago ~ To 8 hrs after (Hiện tại đến 8 tiếng tới)
FROM_HOURS_AGO = 0
TO_HOURS_AFTER = 8

if not username or not password or not sheet_url:
    print("❌ Lỗi: Thiếu USERNAME, PASSWORD hoặc SHEET_URL trong GitHub Secrets!")
    exit(1)

def run():
    tz_vn = timezone(timedelta(hours=7))
    now_vn = datetime.now(tz_vn)
    
    start_time = int((now_vn - timedelta(hours=FROM_HOURS_AGO)).timestamp())
    end_time = int((now_vn + timedelta(hours=TO_HOURS_AFTER)).timestamp())

    print(f"⚡ Kéo Linehaul Trips (Giờ VN: {now_vn.strftime('%H:%M %d/%m/%Y')})")
    print(f"   -> Dải giờ lọc STD: từ {datetime.fromtimestamp(start_time, tz_vn).strftime('%H:%M %d/%m')} đến {datetime.fromtimestamp(end_time, tz_vn).strftime('%H:%M %d/%m')}")

    try:
        with sync_playwright() as p:
            print("1. Khởi chạy trình duyệt Chromium ngầm...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            print("2. Đăng nhập SPX...")
            page.goto("https://spx.shopee.vn/", timeout=60000)
            page.wait_for_load_state("networkidle")

            page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)
            page.locator("input[type='password'], input[name='password']").first.fill(password)
            page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first.click()

            # Chờ hoàn tất đăng nhập theo đúng chuẩn Playwright
            page.wait_for_timeout(8000)

            # Rút trích toàn bộ cookie
            cookies = context.cookies()
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            browser.close()

            # Tự động đồng bộ và vá các token bắt buộc của SPX
            uid_match = re.search(r'(?:spx_uid|fms_user_id)=([^;]+)', cookie_string)
            uid = uid_match.group(1).strip() if uid_match else ''

            uk_match = re.search(r'(?:spx_uk|fms_user_skey)=([^;]+)', cookie_string)
            uk = uk_match.group(1).strip() if uk_match else ''

            if 'spx_uid=' not in cookie_string and uid:
                cookie_string += f"; spx_uid={uid}"
            if 'spx_uk=' not in cookie_string and uk:
                cookie_string += f"; spx_uk={uk}"
            if 'spx_cid=' not in cookie_string:
                cookie_string += "; spx_cid=VN"
            if 'spx_st=' not in cookie_string:
                cookie_string += "; spx_st=1"
            if 'spx-admin-lang=' not in cookie_string:
                cookie_string += "; spx-admin-lang=vi; spx-lang=vi; language=vi"

            csrf_match = re.search(r'csrftoken=([^;]+)', cookie_string)
            csrf_token = csrf_match.group(1).strip() if csrf_match else ""

            print(f"-> Đăng nhập thành công (UID: {uid}, CID: VN, CSRF: {'Có' if csrf_token else 'Không'})")

            req_headers = {
                "app": "FMS Portal",
                "Cookie": cookie_string,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://spx.shopee.vn/admin/transportation/trip",
                "Origin": "https://spx.shopee.vn",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            if csrf_token:
                req_headers["x-csrftoken"] = csrf_token

            all_trips = []
            page_no = 1
            max_pages = 10

            print("3. Đang gửi yêu cầu lấy dữ liệu chuyến xe...")
            while page_no <= max_pages:
                linehaul_url = f"https://spx.shopee.vn/api/admin/transportation/trip/list_v2?station_type=2,3,7,12,14,16,18&trip_station_status=0&pageno={page_no}&count=100&query_type=1&tab_type=3&std={start_time},{end_time}"

                response = requests.get(linehaul_url, headers=req_headers, timeout=30)
                
                if response.status_code != 200:
                    print(f"   -> Lỗi HTTP {response.status_code}: {response.text[:200]}")
                    break

                trip_res = response.json()
                trips = trip_res.get('data', {}).get('list') or trip_res.get('data', {}).get('trips') or []
                
                if not trips:
                    print(f"   -> Hết dữ liệu ở trang {page_no}.")
                    break

                all_trips.extend(trips)
                print(f"   -> Đã lấy thành công Trang {page_no}: {len(trips)} chuyến (Tổng cộng: {len(all_trips)})...")

                if len(trips) < 100:
                    break

                page_no += 1
                time.sleep(0.3)

            print(f"✅ Tổng cộng thu thập được: {len(all_trips)} chuyến xe.")

            if len(all_trips) == 0:
                print("⚠️ Cảnh báo: Không có chuyến xe nào trong khung giờ này.")
                return

            print("4. Đang gửi dữ liệu sang Google Sheets...")
            payload = {
                "action": "sync_linehaul",
                "linehaul_trips": all_trips
            }
            
            res = requests.post(sheet_url, json=payload, timeout=60)
            print(f"Kết quả lưu vào Sheet: {res.text}")

    except Exception as err:
        print(f"❌ Đã xảy ra lỗi: {err}")
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    run()
