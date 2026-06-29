import os
import logging

logger = logging.getLogger(__name__)

# API Token - Đọc từ environment variable, default là token dev
API_TOKEN = os.getenv("API_TOKEN", "srvas_secure_token_123")

# ⚠️ Security Warning cho development
if API_TOKEN == "srvas_secure_token_123":
    logger.warning(
        "⚠️  WARNING: Using default API_TOKEN 'srvas_secure_token_123'! "
        "This is INSECURE for production. "
        "Set environment variable: export API_TOKEN='your_secure_token'"
    )

