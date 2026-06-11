import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_SERVICE_NAME = os.getenv("DB_SERVICE_NAME")

DATABASE_URL = (
    f"oracle+oracledb://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/?service_name={DB_SERVICE_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    echo=True
)