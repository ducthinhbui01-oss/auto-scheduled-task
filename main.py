import os
import time
from playwright.sync_api import sync_playwright

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
sheet_url = os.getenv("SHEET_URL")

def run():
    print("================ BẮT ĐẦU CHẨN ĐOÁN ĐĂNG NHẬP SPX ================")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 1. Bắt gói tin phản hồi của các API đăng nhập
        login_api_logs = []
        page.on("response", lambda res: login_api_logs.append(
            f"[{res.status}] {res.url[:80]}..."
        ) if any(k in res.url.lower() for k in ["login", "auth", "passport", "account"]) else None)

        print("1. Truy cập https://spx.shopee.vn/ ...")
        page.goto("https://spx.shopee.vn/", timeout=60000)
        page.wait_for_load_state("networkidle")

        print("2. Điền thông tin tài khoản...")
        page.locator("input[type='text'], input[name='username'], input[placeholder*='nhập'], input[placeholder*='Username']").first.fill(username)
        page.locator("input[type='password'], input[name='password']").first.fill(password)
        
        print("3. Bấm nút Đăng nhập...")
        page.locator("button[type='submit'], button:has-text('Đăng nhập'), button:has-text('Login')").first.click()

        print("4. Chờ 6 giây để máy chủ xử lý...")
        page.wait_for_timeout(6000)

        # --- BÁO CÁO KẾT QUẢ CHẨN ĐOÁN THỰC TẾ ---
        print("\n---------------- KẾT QUẢ CHẨN ĐOÁN ----------------")
        print(f"📍 URL hiện tại sau khi đăng nhập: {page.url}")

        # Kiểm tra thông báo lỗi trên giao diện (nếu có)
        try:
            alerts = page.locator(".error, .el-message, [class*='error'], [class*='alert'], [class*='tip']").all_text_contents()
            clean_alerts = [a.strip() for a in alerts if a.strip()]
            if clean_alerts:
                print(f"⚠️ Thông báo hiển thị trên màn hình: {clean_alerts}")
            else:
                print("ℹ️ Không có cảnh báo lỗi nào trên giao diện.")
        except:
            pass

        # In danh sách phản hồi từ API đăng nhập
        print(f"🌐 Các API xác thực đã gọi: {login_api_logs}")

        # Rút trích và kiểm tra từng Cookie
        cookies = context.cookies()
        c_dict = {c['name']: c['value'] for c in cookies}
        print(f"\n🍪 Tổng số Cookie thu được: {len(cookies)}")
        print("📋 Danh sách các tên Cookie có trong phiên:")
        for name in sorted(c_dict.keys()):
            # Che bớt giá trị để bảo mật
            val_preview = c_dict[name][:8] + "..." if len(c_dict[name]) > 12 else c_dict[name]
            print(f"   • {name}: {val_preview}")

        # Đánh giá các khóa cốt lõi
        has_uid = 'fms_user_id' in c_dict or 'spx_uid' in c_dict
        has_skey = 'fms_user_skey' in c_dict or 'spx_uk' in c_dict
        has_ec = 'SPC_EC' in c_dict or 'SPC_B_EC' in c_dict

        print("\n================ KẾT LUẬN TỰ ĐỘNG ================")
        print(f"1. Mã User ID (fms_user_id/spx_uid): {'✅ CÓ' if has_uid else '❌ KHÔNG TÌM THẤY'}")
        print(f"2. Khóa phiên (fms_user_skey/spx_uk): {'✅ CÓ' if has_skey else '❌ KHÔNG TÌM THẤY'}")
        print(f"3. Token SPC_EC: {'✅ CÓ' if has_ec else '❌ KHÔNG TÌM THẤY'}")
        print("===================================================\n")

        browser.close()

if __name__ == "__main__":
    run()
