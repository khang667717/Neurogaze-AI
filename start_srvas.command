#!/bin/bash
# Lấy đường dẫn tuyệt đối của thư mục chứa script này
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "======================================"
echo "Khởi động hệ thống SRVAS..."
echo "======================================"

# Gọi run.sh
./run.sh
