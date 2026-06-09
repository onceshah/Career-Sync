from sqlalchemy import text

from app.database.connection import engine


def test_connection():
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT USER FROM dual")
        )

        for row in result:
            print(row)


if __name__ == "__main__":
    test_connection()