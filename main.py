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
    print("⚡ Bắt đầu tiến trình lấy Cookie SPX...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("1. Mở trang đăng nhập SPX...")
        page.goto("https://spx.shopee.vn/", timeout=60000)
        page.wait_for_load_state("networkidle")

        print("2. Điền tài khoản và mật khẩu...")
        page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)
        page.locator("input[type='password'], input[name='password']").first.fill(password)
        
        print("3. Bấm nút Đăng nhập...")
        page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first.click()

        # 4. CHỜ HOÀN TẤT BƯỚC NHẢY SSO ĐỂ LẤY 6 CHÌA KHÓA SPX
        print("4. Đang chờ máy chủ SPX cấp bộ chìa khóa vận hành (fms_user_skey / spx_uid)...")
        user_id = ""
        user_key = ""
        cookie_dict = {}

        for i in range(25):
            time.sleep(1)
            cookies = context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            
            user_id = cookie_dict.get('fms_user_id') or cookie_dict.get('spx_uid') or ''
            user_key = cookie_dict.get('fms_user_skey') or cookie_dict.get('spx_uk') or ''
            
            # Nếu đã có chìa khóa phiên fms_user_skey thì dừng chờ
            if user_key and user_id:
                print(f"-> Đăng nhập thành công! Nhận được User ID: {user_id} sau {i+1} giây.")
                break
            
            # Nếu sau 5s vẫn đang ở cổng auth thì kích hoạt chuyển tiếp về SPX
            if i == 5 and not user_key:
                print("-> Đang thực hiện chuyển hướng hoàn tất SSO về SPX...")
                try:
                    page.goto("https://spx.shopee.vn/api/admin/basicserver/ops_tob_login?refer=https://spx.shopee.vn/%23/", timeout=30000)
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass

        browser.close()

        # Kiểm tra điều kiện bắt buộc
        if not user_key or not user_id:
            print("❌ THẤT BẠI: Chưa nhận được fms_user_skey từ SPX. Dừng gửi để tránh gửi cookie lỗi sang Sheet.")
            exit(1)

        # 5. ĐỒNG BỘ VÀ TẠO CHUỖI COOKIE HOÀN CHỈNH
        cookie_dict['spx_uid'] = str(user_id)
        cookie_dict['fms_user_id'] = str(user_id)
        cookie_dict['spx_uk'] = str(user_key)
        cookie_dict['fms_user_skey'] = str(user_key)

        cookie_dict['spx_cid'] = 'VN'
        cookie_dict['spx_st'] = '1'
        cookie_dict['language'] = 'vi'
        cookie_dict['spx-lang'] = 'vi'
        cookie_dict['spx-admin-lang'] = 'vi'

        cookie_string = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

        print("\n---------------- KẾT QUẢ THU THẬP ----------------")
        print(f"✅ User ID: {user_id}")
        print(f"✅ Khóa phiên (fms_user_skey): {user_key[:10]}...")
        print(f"✅ Tổng số Cookie: {len(cookie_dict)}")
        print("--------------------------------------------------\n")

        # 6. GỬI SANG GOOGLE SHEETS
        print("5. Đang gửi Cookie hợp lệ sang Google Sheets...")
        payload = {
            "status": "Lấy Cookie SPX Thành Công",
            "result": cookie_string
        }
        
        sheet_res = requests.post(sheet_url, json=payload, timeout=30)
        print(f"Kết quả lưu vào Sheet: {sheet_res.text}")

if __name__ == "__main__":
    run()
