import os
import mysql.connector
from dotenv import load_dotenv

from logger import db_logger

load_dotenv()


def create_db_connection():
    host = os.getenv("DB_HOST")
    port = int(os.getenv("DB_PORT", "3306"))
    name = os.getenv("DB_NAME")

    db_logger.info("Connecting to DB %s@%s:%s", name, host, port)
    try:
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=name,
            connection_timeout=10,
        )
        db_logger.info("Database connected successfully")
        return connection
    except mysql.connector.Error:
        db_logger.exception("Database connection failed (%s:%s/%s)", host, port, name)
        return None