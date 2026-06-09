from sqlalchemy import create_engine

DATABASE_URL = (
    "oracle+oracledb://email_triage:EmailTriage123"
    "@localhost:1521/?service_name=XEPDB1"
)

engine = create_engine(
    DATABASE_URL,
    echo=True
)