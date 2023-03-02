import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
# engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
user = os.getenv("MYSQLUSER", default="root")
password = os.getenv("MYSQLPASSWORD", default="root")
host = os.getenv("MYSQLHOST", default="localhost")
db = os.getenv("MYSQLDATABASE", default="moses")
port = os.getenv("MYSQLPORT", default="3306")
MYSQL_URL = os.getenv("MYSQL_URL", default="Empty URL")
print(f"MYSQL_URL {MYSQL_URL}")

# SQLALCHEMY_DATABASE_URL = 'mysql+pymysql://root:root@localhost:3306/moses'
# mysql://root:KCPFonJgXYHjsEYAmQ5H@containers-us-west-118.railway.app:8002/railway
SQLALCHEMY_DATABASE_URL = f'mysql+pymysql://{user}:{password}@{host}:{port}/{db}'
print(f"Sql alchemy url {SQLALCHEMY_DATABASE_URL}")
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
