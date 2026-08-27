import os
import time
import requests
from playwright.sync_api import sync_playwright

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
sheet_url = os.getenv("SHEET_URL")

if not username or not password or not sheet_url:
    print("❌ Lỗi: Thiếu USERNAME, PASSWORD hoặc SHEET_URL trong GitHub Secrets!")
    exit(1)

def run():
    print("⚡ Bắt đầu tiến trình lấy Cookie SPX chuẩn xác...")
    try:
        with sync_playwright() as p:
            print("1. Khởi chạy trình duyệt Chromium ngầm...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # --- BƯỚC 1: ĐĂNG NHẬP QUA CỔNG SHOPEE BUSINESS ---
            print("2. Truy cập cổng đăng nhập SPX...")
            page.goto("https://spx.shopee.vn/", timeout=60000)
            page.wait_for_load_state("networkidle")

            page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)
            page.locator("input[type='password'], input[name='password']").first.fill(password)
            
            print("3. Gửi thông tin tài khoản...")
            page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first.click()
            page.wait_for_timeout(4000)

            # --- BƯỚC 2: THỰC HIỆN CÚ NHẢY SSO ĐỂ ĐỔI SANG BỘ 6 CHÌA KHÓA SPX ---
            print("4. Đang đổi mã xác thực SSO sang bộ chìa khóa vận hành SPX...")
            page.goto("https://spx.shopee.vn/api/admin/basicserver/ops_tob_login?refer=https://spx.shopee.vn/%23/", timeout=60000)
            page.wait_for_load_state("networkidle")

            # --- BƯỚC 3: CHỐT CHẶN AN TOÀN (CHỜ NHẬN ĐỦ fms_user_skey & spx_uid) ---
            print("-> Đang chờ máy chủ cấp đủ bộ chìa khóa fms_user_skey & spx_uid...")
            user_id = ""
            user_key = ""
            cookie_dict = {}

            for i in range(15):
                time.sleep(1)
                cookies = context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                
                user_id = cookie_dict.get('fms_user_id') or cookie_dict.get('spx_uid') or ''
                user_key = cookie_dict.get('fms_user_skey') or cookie_dict.get('spx_uk') or ''
                
                # Khi có đủ User ID và Session Key -> Đạt chuẩn 100%
                if user_id and user_key:
                    print(f"✅ ĐÃ NHẬN ĐỦ BỘ CHÌA KHÓA SPX sau {i+1} giây! (User ID: {user_id})")
                    break

            browser.close()

            if not user_id or not user_key:
                print("❌ THẤT BẠI: Chưa nhận được mã phiên fms_user_skey từ SPX. Dừng tiến trình để tránh gửi cookie lỗi.")
                exit(1)

            # --- BƯỚC 4: ĐỒNG BỘ ĐẦY ĐỦ CÁC KHÓA BẮT BUỘC ---
            cookie_dict['spx_uid'] = str(user_id)
            cookie_dict['fms_user_id'] = str(user_id)
            cookie_dict['spx_uk'] = str(user_key)
            cookie_dict['fms_user_skey'] = str(user_key)
            
            # Gán tên hiển thị
            dn = cookie_dict.get('fms_display_name') or cookie_dict.get('spx_dn') or username
            cookie_dict['fms_display_name'] = str(dn)
            cookie_dict['spx_dn'] = str(dn)

            cookie_dict['spx_cid'] = 'VN'
            cookie_dict['spx_st'] = '1'
            cookie_dict['language'] = 'vi'
            cookie_dict['spx-lang'] = 'vi'
            cookie_dict['spx-admin-lang'] = 'vi'

            cookie_string = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

            print(f"-> Chuỗi Cookie hoàn chỉnh có {len(cookie_dict)} khóa (Có đủ fms_user_skey, spx_uid, spx_uk).")

            # --- BƯỚC 5: GỬI COOKIE CHUẨN VỀ GOOGLE SHEETS ---
            print("5. Đang lưu Cookie mới vào Google Sheets...")
            payload = {
                "status": "Lấy Cookie SPX Thành Công",
                "result": cookie_string
            }
            
            sheet_res = requests.post(sheet_url, json=payload, timeout=30)
            print(f"Kết quả lưu vào Sheet: {sheet_res.text}")

    except Exception as err:
        print(f"❌ Đã xảy ra lỗi: {err}")
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    run()
