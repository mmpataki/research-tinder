from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Migrate: add new columns to existing papers table if missing
    new_cols = [
        ("source", "VARCHAR DEFAULT 'arxiv'"),
        ("has_artifacts", "BOOLEAN DEFAULT 0"),
        ("artifact_links", "TEXT"),
    ]
    async with engine.connect() as conn:
        from sqlalchemy import text
        for col, definition in new_cols:
            try:
                await conn.execute(text(f"ALTER TABLE papers ADD COLUMN {col} {definition}"))
                await conn.commit()
            except Exception:
                pass  # column already exists
