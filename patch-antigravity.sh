# 1. Tạo bản sao ứng dụng đã được vá lỗi
sudo cp -R "/Applications/Antigravity IDE.app" "/Applications/Antigravity IDE-patched.app"

# 2. Xóa bỏ thuộc tính cách ly của macOS
sudo xattr -dr com.apple.quarantine "/Applications/Antigravity IDE-patched.app"

# 3. Tạo file cấu hình quyền hạn (Entitlements)
cat > /tmp/antigravity-plugin.entitlements <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "https://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
<key>com.apple.security.cs.allow-jit</key>
<true/>
<key>com.apple.security.cs.disable-library-validation</key>
<true/>
</dict>
</plist>
PLIST

# 4. Định nghĩa chính xác đường dẫn Helper trên máy của bạn
HELPER="/Applications/Antigravity IDE-patched.app/Contents/Frameworks/Antigravity IDE Helper (Plugin).app"

# 5. Ký lại mã nguồn cho Helper và ứng dụng chính
sudo codesign --force --sign - --entitlements /tmp/antigravity-plugin.entitlements "$HELPER"
sudo codesign --force --sign - "/Applications/Antigravity IDE-patched.app"
