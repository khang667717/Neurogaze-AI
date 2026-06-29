#!/usr/bin/env python3
"""
run_backend.py - Script to run SRVAS backend
Usage: python3 run_backend.py
"""
import sys
import os

# Thêm backend directory vào path để import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Import và chạy backend
if __name__ == "__main__":
    import uvicorn
    from backend.main import app
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
