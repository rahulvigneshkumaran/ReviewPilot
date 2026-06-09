import asyncio
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_db
from app.core.security import create_access_token, encrypt_token
from app.db.base import Base
from app.db.models import User

# In-memory SQLite for self-contained, fast async tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create async sqlite engine for testing."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Initialize the database schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Patch the global database objects in app.core.database
    import app.core.database
    
    test_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    old_engine = app.core.database.engine
    old_session_factory = app.core.database.async_session_factory
    
    app.core.database.engine = engine
    app.core.database.async_session_factory = test_session_factory

    # Patch the global Qdrant client in app.services.rag to use in-memory vector database
    import app.services.rag
    from qdrant_client import QdrantClient
    
    old_qdrant_client = app.services.rag.rag_service.client
    old_qdrant_is_test = app.services.rag.rag_service.is_test
    
    app.services.rag.rag_service.client = QdrantClient(location=":memory:")
    app.services.rag.rag_service.is_test = True
        
    yield engine
    
    # Restore original database and Qdrant connections
    app.core.database.engine = old_engine
    app.core.database.async_session_factory = old_session_factory
    app.services.rag.rag_service.client = old_qdrant_client
    app.services.rag.rag_service.is_test = old_qdrant_is_test
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session for a single test case."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        # Clean up database after each test to ensure test isolation
        async with test_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())

@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Mock FastAPI client that overrides get_db to use the test database session."""
    
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    # Use ASGITransport to test FastAPI application locally
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"
    ) as async_client:
        yield async_client
        
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a dummy user in the database for authentication checks."""
    user = User(
        email="developer@reviewpilot.io",
        github_id="998877",
        github_username="testdeveloper",
        avatar_url="https://github.com/avatar.png",
        encrypted_access_token=encrypt_token("gho_mock_access_token_12345"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Generate auth headers using JWT token for test user authorization."""
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}
