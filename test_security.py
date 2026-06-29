#!/usr/bin/env python3
"""
test_security.py - Script kiểm tra các tính năng bảo mật mới
Kiểm tra: API token authentication, rate limiting, etc.
"""

import requests
import json
import time
from typing import Tuple

API_URL = "http://localhost:8000"
API_TOKEN = "srvas_secure_token_123"
WRONG_TOKEN = "wrong_token_123"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_test(name: str):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}Test: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")

def print_result(success: bool, message: str):
    status = f"{Colors.GREEN}✅ PASS{Colors.END}" if success else f"{Colors.RED}❌ FAIL{Colors.END}"
    print(f"{status}: {message}")

def test_1_valid_token_in_header() -> bool:
    """Test 1: Valid token trong header X-API-Key"""
    print_test("Valid Token in Header")
    
    try:
        response = requests.post(
            f"{API_URL}/api/events",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": API_TOKEN
            },
            json={
                "event_code": "PERSON_DETECTED",
                "session_id": "test_session_1",
                "confidence": 0.95,
                "timestamp": time.time(),
                "payload": {}
            },
            timeout=5
        )
        
        success = response.status_code == 200
        print_result(success, f"Status: {response.status_code} - {response.text}")
        return success
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False

def test_2_missing_token_header() -> bool:
    """Test 2: Token header bị thiếu"""
    print_test("Missing Token Header")
    
    try:
        response = requests.post(
            f"{API_URL}/api/events",
            headers={"Content-Type": "application/json"},
            json={"event_code": "TEST"},
            timeout=5
        )
        
        success = response.status_code == 401
        print_result(success, f"Status: {response.status_code} (Expected: 401)")
        if response.status_code == 401:
            print(f"  └─ Error: {response.json()['detail']}")
        return success
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False

def test_3_invalid_token() -> bool:
    """Test 3: Token không hợp lệ"""
    print_test("Invalid Token")
    
    try:
        response = requests.post(
            f"{API_URL}/api/events",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": WRONG_TOKEN
            },
            json={"event_code": "TEST"},
            timeout=5
        )
        
        success = response.status_code == 401
        print_result(success, f"Status: {response.status_code} (Expected: 401)")
        if response.status_code == 401:
            print(f"  └─ Error: {response.json()['detail']}")
        return success
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False

def test_4_query_param_deprecated() -> bool:
    """Test 4: Query parameter không còn hoạt động (deprecated)"""
    print_test("Query Parameter (Deprecated)")
    
    try:
        response = requests.post(
            f"{API_URL}/api/events?token={API_TOKEN}",
            headers={"Content-Type": "application/json"},
            json={"event_code": "TEST"},
            timeout=5
        )
        
        # Nếu query param không được hỗ trợ, phải nhận 401
        success = response.status_code == 401
        print_result(success, f"Status: {response.status_code} (Expected: 401)")
        if response.status_code == 401:
            print(f"  └─ Query params không còn được hỗ trợ ✅")
        else:
            print(f"  └─ ⚠️  Query params vẫn hoạt động (có thể bảo lưu cho compatibility)")
        return success
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False

def test_5_rate_limiting() -> bool:
    """Test 5: Rate limiting - verify it rejects excessive requests"""
    print_test("Rate Limiting")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_TOKEN
        }
        
        # Gửi 120 request nhanh liên tiếp đến endpoint test rate limit
        # Endpoint này có giới hạn 100/minute
        status_codes = []
        for i in range(120):
            try:
                response = requests.post(
                    f"{API_URL}/api/test_rate_limit",
                    headers=headers,
                    json={},
                    timeout=5
                )
                status_codes.append(response.status_code)
            except requests.exceptions.Timeout:
                status_codes.append(-1)  # Timeout
        
        # Kiểm tra xem có 429 status code trong kết quả
        has_rate_limit_errors = 429 in status_codes
        has_successful_requests = 200 in status_codes
        
        if has_rate_limit_errors and has_successful_requests:
            print(f"  └─ Sent {len(status_codes)} requests")
            print(f"  └─ Successful (200): {status_codes.count(200)}")
            print(f"  └─ Rate limited (429): {status_codes.count(429)}")
            print(f"{Colors.GREEN}✅{Colors.END} Rate limiting is active and working!")
            success = True
        else:
            print(f"  └─ Error: Expected both 200 and 429 responses")
            print(f"  └─ Got: 200={status_codes.count(200)}, 429={status_codes.count(429)}")
            success = False
        
        print_result(success, f"Rate limiting functionality verified")
        return success
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False

def test_6_websocket_token() -> bool:
    """Test 6: WebSocket vẫn sử dụng query parameter"""
    print_test("WebSocket Token Parameter")
    
    try:
        import websockets
        import asyncio
        
        async def test_ws():
            try:
                # WebSocket endpoint
                ws_url = f"ws://localhost:8000/ws/dashboard?token={API_TOKEN}"
                async with websockets.connect(ws_url) as websocket:
                    # Nếu kết nối thành công, token hợp lệ
                    await websocket.close()
                    return True
            except Exception as e:
                print(f"  └─ Error: {str(e)}")
                return False
        
        success = asyncio.run(test_ws())
        print_result(success, "WebSocket connection established with token parameter")
        return success
    except ImportError:
        print_result(False, "websockets library not installed - skipping test")
        return False
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False

def main():
    print(f"{Colors.YELLOW}{'='*60}{Colors.END}")
    print(f"{Colors.YELLOW}SRVAS Security Updates - Test Suite{Colors.END}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.END}")
    
    # Kiểm tra backend có chạy không
    try:
        response = requests.get(f"{API_URL}/api/dashboard", timeout=5)
        print(f"\n{Colors.GREEN}✅ Backend is running at {API_URL}{Colors.END}")
    except:
        print(f"\n{Colors.RED}❌ Backend not running at {API_URL}{Colors.END}")
        print(f"   Please start the backend: python backend/main.py")
        return
    
    # Chạy các test
    results = []
    results.append(("Valid Token in Header", test_1_valid_token_in_header()))
    results.append(("Missing Token Header", test_2_missing_token_header()))
    results.append(("Invalid Token", test_3_invalid_token()))
    results.append(("Query Parameter Deprecated", test_4_query_param_deprecated()))
    results.append(("Rate Limiting", test_5_rate_limiting()))
    
    # Bỏ qua WebSocket test nếu không có websockets library
    try:
        import websockets
        results.append(("WebSocket Token Parameter", test_6_websocket_token()))
    except ImportError:
        print(f"\n{Colors.YELLOW}⚠️  WebSocket test skipped (install: pip install websockets){Colors.END}")
    
    # Tóm tắt
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}Test Summary{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
        print(f"{status}: {test_name}")
    
    print(f"\n{Colors.BLUE}Result: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}🎉 All security tests passed!{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠️  {total - passed} test(s) failed{Colors.END}")

if __name__ == "__main__":
    main()
