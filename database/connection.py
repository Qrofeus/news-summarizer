import pymysql
import pymysql.cursors

from config import Config


def get_connection(config: Config) -> pymysql.Connection:
    return pymysql.connect(
        host=config.mysql_host,
        user=config.mysql_user,
        password=config.mysql_password,
        database=config.mysql_database,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )
