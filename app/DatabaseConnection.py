import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
# engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
user = os.getenv("MYSQL_USER", default="root")
password = os.getenv("MYSQL_PASSWORD", default="root")
host = os.getenv("MYSQL_HOST", default="localhost")
db = os.getenv("MYSQL_DATABASE", default="moses")

# SQLALCHEMY_DATABASE_URL = 'mysql+pymysql://root:root@localhost:3306/moses'
SQLALCHEMY_DATABASE_URL = f'mysql+pymysql://{user}:{password}@{host}:3306/{db}'
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
