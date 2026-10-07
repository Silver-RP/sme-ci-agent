"""Kết nối DB: lấy từ biến môi trường DATABASE_URL, mặc định trùng .env.example (synthetic)."""

import os

DEFAULT_DATABASE_URL = "postgresql+psycopg://sme:sme@localhost:5432/sme_ci"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
