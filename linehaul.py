import os
import re
import time
import json
import math
import traceback
import concurrent.futures
from datetime import datetime, timedelta, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright.sync_api import sync_playwright

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
sheet_url = os.getenv("SHEET_URL")

# --- CẤU HÌNH QUY MÔ DỮ LIỆU & KHUNG GIỜ ---
FROM_HOURS_AGO = 0    # Quét lùi 2 tiếng trước để không sót xe đầu ca
TO_HOURS_AFTER = 8    # Quét tới 8 tiếng tiếp theo
MAX_PAGES = 60        # Hỗ trợ tối đa 60 trang (~6.000 chuyến xe)
MAX_WORKERS = 5       # 5 luồng song song tối ưu

# DANH SÁCH 24 CỘT CẦN GIỮ LẠI
TARGET_COLUMNS = [
    "id", "trip_number", "trip_name", "schedule_id", "planning_name", "schedule_version",
    "label", "trip_station", "next_station_list", "next_station_name_list", "next_station_code_list",
    "vehicle_type", "vehicle_type_name", "origin_vehicle_type", "agency_id", "agency_name",
    "to_packed_quantity", "order_packed_quantity", "to_loaded_quantity", "order_loaded_quantity",
    "ctime", "mtime", "cost_type", "handover_enable"
]

if not username or not password or not sheet_url:
    print("❌ Lỗi: Thiếu USERNAME, PASSWORD hoặc SHEET_URL trong GitHub Secrets!")
    exit(1)

# Tạo Session tối ưu tốc độ
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=0.3,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retries)
session.mount('https://', adapter)
session.mount('http://', adapter)

def format_trip_station(st_list, tz_vn):
    """Bóc tách mảng trip_station thành lộ trình: Trạm 1 (STD) ➔ Trạm 2 (STA)"""
    if not isinstance(st_list, list) or len(st_list) == 0:
        return ""
    parts = []
    for st in st_list:
        name = st.get('station_name') or str(st.get('station', ''))
        std = st.get('std', 0)
        sta = st.get('sta', 0)
        time_strs = []
        if std and std > 1000000000:
            time_strs.append(f"STD: {datetime.fromtimestamp(std, tz_vn).strftime('%d/%m %H:%M')}")
        if sta and sta > 1000000000:
            time_strs.append(f"STA: {datetime.fromtimestamp(sta, tz_vn).strftime('%d/%m %H:%M')}")
        time_info = f" ({' | '.join(time_strs)})" if time_strs else ""
        parts.append(f"{name}{time_info}")
    return " ➔ ".join(parts)

def format_item_to_row(item, tz_vn):
    """Chuẩn hóa dữ liệu 1 chuyến xe thành 1 hàng 24 cột sạch sẽ"""
    row = []
    for col in TARGET_COLUMNS:
        val = item.get(col)
        
        if col == "trip_station":
            row.append(format_trip_station(val, tz_vn))
        elif col in ["next_station_list", "next_station_name_list", "next_station_code_list"]:
            if isinstance(val, list):
                row.append(", ".join(map(str, val)))
            else:
                row.append(str(val) if val is not None else "")
        elif col in ["ctime", "mtime"] and isinstance(val, (int, float)) and val > 1000000000:
            val_str = datetime.fromtimestamp(val, tz_vn).strftime('%d/%m/%Y %H:%M:%S')
            row.append(val_str)
        elif isinstance(val, bool):
            row.append("TRUE" if val else "FALSE")
        elif isinstance(val, (dict, list)):
            row.append(json.dumps(val, ensure_ascii=False))
        else:
            row.append(str(val) if val is not None else "")
            
    return row

def fetch_page(page_no, base_url, req_headers):
    """Tải 1 trang dữ liệu sử dụng Connection Pool"""
    url = f"{base_url}&pageno={page_no}&count=100"
    try:
        res = session.get(url, headers=req_headers, timeout=25)
        if res.status_code == 200:
            data = res.json()
            return data.get('data', {}).get('list') or data.get('data', {}).get('trips') or []
    except:
        pass
    return []

def run():
    tz_vn = timezone(timedelta(hours=7))
    now_vn = datetime.now(tz_vn)
    
    start_time = int((now_vn - timedelta(hours=FROM_HOURS_AGO)).timestamp())
    end_time = int((now_vn + timedelta(hours=TO_HOURS_AFTER)).timestamp())

    print(f"⚡ Bắt đầu kéo Linehaul Toàn Bộ Các Hub (Giờ VN: {now_vn.strftime('%H:%M %d/%m/%Y')})")
    print(f"   -> Dải giờ lọc STD: từ {datetime.fromtimestamp(start_time, tz_vn).strftime('%H:%M %d/%m')} đến {datetime.fromtimestamp(end_time, tz_vn).strftime('%H:%M %d/%m')}")

    try:
        # BƯỚC 1: ĐĂNG NHẬP VÀ CHỜ NHẬN ĐỦ USER ID
        with sync_playwright() as p:
            print("1. Khởi chạy trình duyệt Chromium đăng nhập SPX...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            page.goto("https://spx.shopee.vn/", timeout=60000)
            page.wait_for_load_state("networkidle")

            page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)
            page.locator("input[type='password'], input[name='password']").first.fill(password)
            page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first.click()
            
            # Chờ máy chủ xác nhận đăng nhập và cấp mã fms_user_id
            print("-> Đang chờ máy chủ xác nhận đăng nhập...")
            user_id = ""
            user_key = ""
            for _ in range(15):
                time.sleep(1)
                c_dict = {c['name']: c['value'] for c in context.cookies()}
                user_id = c_dict.get('fms_user_id') or c_dict.get('spx_uid') or ''
                user_key = c_dict.get('fms_user_skey') or c_dict.get('spx_uk') or ''
                if user_id:
                    print(f"-> Xác nhận đăng nhập thành công! User ID: {user_id}")
                    break

            # Truy cập trang Linehaul để kích hoạt toàn bộ token FMS
            page.goto("https://spx.shopee.vn/admin/transportation/trip", timeout=60000)
            page.wait_for_load_state("networkidle")
            time.sleep(3)

            cookies = context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            browser.close()

        # BƯỚC 2: TỰ ĐỘNG VÁ ĐỦ BỘ 4 THÔNG SỐ SPX GATEWAY
        if not user_id:
            user_id = cookie_dict.get('fms_user_id') or cookie_dict.get('spx_uid') or ''
            user_key = cookie_dict.get('fms_user_skey') or cookie_dict.get('spx_uk') or ''

        if user_id:
            cookie_dict['spx_uid'] = str(user_id)
            cookie_dict['fms_user_id'] = str(user_id)
        if user_key:
            cookie_dict['spx_uk'] = str(user_key)
            cookie_dict['fms_user_skey'] = str(user_key)

        cookie_dict['spx_cid'] = 'VN'
        cookie_dict['spx_st'] = '1'
        cookie_dict['language'] = 'vi'
        cookie_dict['spx-lang'] = 'vi'
        cookie_dict['spx-admin-lang'] = 'vi'

        cookie_string = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
        csrf_token = cookie_dict.get('csrftoken', '')

        print(f"-> Chuỗi Cookie đầy đủ (User ID: {user_id}, CSRF: {'Có' if csrf_token else 'Không'})")

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

        # BƯỚC 3: KÉO ĐA LUỒNG TẤT CẢ CÁC HUB
        station_types = "2,3,7,12,14,16,18"
        base_api_url = f"https://spx.shopee.vn/api/admin/transportation/trip/list_v2?station_type={station_types}&trip_station_status=0&query_type=1&tab_type=3&std={start_time},{end_time}"

        print("2. Đang kiểm tra tổng số chuyến xe trên toàn hệ thống...")
        p1_resp = session.get(f"{base_api_url}&pageno=1&count=100", headers=req_headers, timeout=30)
        
        if p1_resp.status_code != 200:
            print(f"❌ Lỗi phản hồi API: {p1_resp.status_code} - {p1_resp.text[:300]}")
            return

        p1_res = p1_resp.json()
        data_obj = p1_res.get('data') if isinstance(p1_res.get('data'), dict) else {}
        total_trips = data_obj.get('total', 0)
        p1_trips = data_obj.get('list') or data_obj.get('trips') or []
        
        all_trips = list(p1_trips)
        total_pages = min(math.ceil(total_trips / 100), MAX_PAGES) if total_trips > 0 else 1

        print(f"-> Hệ thống tìm thấy: {total_trips} chuyến xe (~{total_pages} trang).")

        if total_pages > 1:
            print(f"3. Đang mở {MAX_WORKERS} luồng tối ưu kéo song song từ trang 2 đến {total_pages}...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_page = {
                    executor.submit(fetch_page, p_no, base_api_url, req_headers): p_no 
                    for p_no in range(2, total_pages + 1)
                }
                for future in concurrent.futures.as_completed(future_to_page):
                    res_list = future.result()
                    all_trips.extend(res_list)

        print(f"✅ Thu thập thành công: {len(all_trips)} / {total_trips} chuyến xe từ tất cả các Hub!")

        if len(all_trips) == 0:
            print("⚠️ Cảnh báo: Không có chuyến xe nào trong khung giờ này.")
            return

        # BƯỚC 4: BÓC TÁCH 24 CỘT VÀ GỬI SANG GOOGLE SHEETS
        print("4. Đang bóc tách và định dạng 24 cột dữ liệu...")
        rows_data = [format_item_to_row(t, tz_vn) for t in all_trips]

        print("5. Đang gửi dữ liệu siêu tốc sang Google Sheets...")
        payload = {
            "action": "sync_linehaul_fast",
            "headers": TARGET_COLUMNS,
            "rows": rows_data
        }
        
        res = session.post(sheet_url, json=payload, timeout=180)
        print(f"Kết quả lưu vào Sheet: {res.text}")

    except Exception as err:
        print(f"❌ Đã xảy ra lỗi: {err}")
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    run()
