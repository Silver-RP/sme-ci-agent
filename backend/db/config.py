"""Kết nối DB: lấy từ biến môi trường DATABASE_URL, mặc định trùng .env.example (synthetic)."""

import os

DEFAULT_DATABASE_URL = "postgresql+psycopg://sme:sme@localhost:5432/sme_ci"

# Giới hạn pool của engine dùng chung (H-37): tối đa POOL_SIZE + MAX_OVERFLOW kết nối cho cả backend.
DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 5


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def get_pool_size() -> int:
    return int(os.environ.get("DB_POOL_SIZE") or DEFAULT_POOL_SIZE)


def get_max_overflow() -> int:
    return int(os.environ.get("DB_MAX_OVERFLOW") or DEFAULT_MAX_OVERFLOW)


def max_connections() -> int:
    return get_pool_size() + get_max_overflow()
