
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/trainflow")
engine = create_engine(DATABASE_URL)

def migrate_cache_table():
    print("MIGRATING: Adding 'llm_request_cache' table...")
    
    # Check if exists
    with engine.connect() as conn:
        res = conn.execute(text("SELECT to_regclass('public.llm_request_cache')")).scalar()
        if res:
            print("  - Table already exists. Skipping.")
            return

        print("  - Creating table...")
        sql = """
        CREATE TABLE llm_request_cache (
            id SERIAL PRIMARY KEY,
            request_hash VARCHAR UNIQUE,
            prompt_content TEXT,
            system_content TEXT,
            response_json JSON,
            model VARCHAR,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc')
        );
        CREATE INDEX ix_llm_request_cache_request_hash ON llm_request_cache (request_hash);
        """
        conn.execute(text(sql))
        conn.commit()
        print("  - SUCCESS: Table created.")

if __name__ == "__main__":
    migrate_cache_table()
