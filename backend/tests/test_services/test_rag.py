import pytest
from sqlalchemy import select

from app.db.models import RAGDocument
from app.services.rag import rag_service

@pytest.mark.asyncio
async def test_rag_seeding_and_retrieval(db_session):
    """Test that guidelines can be seeded into Qdrant/Postgres, and retrieved semantically."""
    # 1. Seeding guidelines from resources/guidelines.json
    await rag_service.seed_guidelines(db_session)
    
    # Verify records exist in PostgreSQL RAGDocument table
    query = select(RAGDocument)
    result = await db_session.execute(query)
    docs = result.scalars().all()
    
    assert len(docs) > 0
    categories = {doc.rule_category for doc in docs}
    assert "SECURITY" in categories
    assert "SOLID" in categories
    
    # 2. Verify collection exists in in-memory Qdrant client
    collections = rag_service.client.get_collections()
    collection_names = [col.name for col in collections.collections]
    assert rag_service.collection_name in collection_names
    
    # 3. Test semantic retrieval match
    # Query containing SQL Injection text should match the SQL injection guideline
    query_text = "Avoid sql injection vulnerabilities"
    results = await rag_service.retrieve_relevant_guidelines(query_text, limit=1)
    
    assert len(results) == 1
    assert "SQL Injection" in results[0]

@pytest.mark.asyncio
async def test_rag_retrieval_empty_query():
    """Verify that retrieval handles empty inputs gracefully without throwing exceptions."""
    results = await rag_service.retrieve_relevant_guidelines("", limit=2)
    assert isinstance(results, list)
