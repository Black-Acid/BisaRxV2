import sqlalchemy as sql
from sqlalchemy import orm, create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import OperationalError
import time

DB_URL = "postgresql://neondb_owner:npg_aIOdp1xz8ZwL@ep-crimson-glade-abzvwvo4-pooler.eu-west-2.aws.neon.tech/bisarxdbv2?sslmode=require&channel_binding=require"
def create_engine_with_retry(url, retries=5, delay=2):
    for attempt in range(retries):
        try:
            engine = create_engine(
                url,
                pool_pre_ping=True,  # ensures idle connections are checked
                pool_size=5,         # adjust based on expected load
                max_overflow=10
            )
            # Test the connection
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            return engine
        except OperationalError as e:
            print(f"Database connection failed (attempt {attempt + 1}/{retries}): {e}")
            time.sleep(delay)
    raise Exception("Could not connect to the database after several attempts.")

# Create resilient engine
engine = create_engine_with_retry(DB_URL)

SessionLocal = orm.sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass