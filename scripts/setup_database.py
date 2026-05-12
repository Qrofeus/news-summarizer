"""Run once against qrofeus.dev MySQL to create the database and tables."""
from pathlib import Path

import pymysql

from config import Config


def setup_database() -> None:
    config = Config.from_env()
    schema_path = Path(__file__).parent.parent / 'database' / 'schema.sql'
    sql = schema_path.read_text(encoding='utf-8')

    # Connect without specifying a database so CREATE DATABASE succeeds.
    conn = pymysql.connect(
        host=config.mysql_host,
        user=config.mysql_user,
        password=config.mysql_password,
        charset='utf8mb4',
    )
    try:
        with conn.cursor() as cursor:
            for statement in sql.split(';'):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)
                    conn.commit()
    finally:
        conn.close()

    print('Database setup complete.')


if __name__ == '__main__':
    setup_database()
