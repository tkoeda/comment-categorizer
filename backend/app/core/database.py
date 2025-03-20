from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings

# For a local SQLite database:


engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
