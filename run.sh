#!/bin/bash

# Exit on absolute errors
set -e

# 1. Kích hoạt môi trường ảo
if [ -d "venv" ]; then
    echo "🤖 Đang kích hoạt môi trường ảo (venv)..."
    source venv/bin/activate
else
    echo "❌ Không tìm thấy thư mục venv. Hãy chạy setup trước."
    exit 1
fi

# 2. Khởi chạy Backend Server (FastAPI) trong background
echo "🚀 Đang khởi động Backend Server..."
python3 run_backend.py &
BACKEND_PID=$!

# Đăng ký bẫy tín hiệu (trap) để tự động tắt backend khi tắt script này (Ctrl+C hoặc khi script kết thúc)
trap "echo -e '\n🛑 Đang tắt Backend Server (PID: $BACKEND_PID)...'; kill $BACKEND_PID 2>/dev/null; echo '👋 Đã dọn dẹp xong. Tạm biệt!'" EXIT

# Đợi 4 giây để Backend khởi tạo cổng 8000
sleep 4

# 3. Mở trình duyệt hiển thị Dashboard
echo "🌐 Đang mở Dashboard trên trình duyệt..."
open http://localhost:8000/

# 4. Khởi chạy Computer Vision (Webcam tracking) ở foreground và lưu log
echo "📷 Đang chạy Module Computer Vision (nhấn Ctrl+C trong terminal này để dừng toàn bộ hệ thống)..."
python3 cv/main.py 2>&1 | tee cv.log
