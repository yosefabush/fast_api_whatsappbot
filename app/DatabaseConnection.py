import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_utils import database_exists, create_database

# SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
# engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
user = os.getenv("MYSQLUSER", default="root")
password = os.getenv("MYSQLPASSWORD", default="root")
host = os.getenv("MYSQLHOST", default="localhost")
db = os.getenv("MYSQLDATABASE", default="moses")
port = os.getenv("MYSQLPORT", default="3306")
MYSQL_URL = os.getenv("MYSQL_URL", default=None)
print(f"MYSQL_URL: '{MYSQL_URL}'")

SQLALCHEMY_DATABASE_URL = f'mysql+pymysql://{user}:{password}@{host}:{port}/{db}'

# SQLALCHEMY_DATABASE_URL = 'mysql+pymysql://root:root@localhost:3306/moses'
# mysql://root:KCPFonJgXYHjsEYAmQ5H@containers-us-west-118.railway.app:8002/railway
if MYSQL_URL is None:
    print("Default mysql")
    SQLALCHEMY_DATABASE_URL = f'mysql+pymysql://{user}:{password}@{host}:{port}/{db}'
else:
    print("From Server mysql")
    # SQLALCHEMY_DATABASE_URL = MYSQL_URL

print(f"Full Sql alchemy connection string: '{SQLALCHEMY_DATABASE_URL}'")
engine = create_engine(SQLALCHEMY_DATABASE_URL)

if not database_exists(engine.url):
    print("New Data Base were created!")
    create_database(engine.url)
else:
    # Connect the database if exists.
    print("Data Base exist!")
    engine.connect()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
