import os
import json
import uuid
import hashlib
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings
from app.db.models import RAGDocument

class RAGService:
    def __init__(self):
        self.collection_name = "guidelines"
        self.vector_size = 384  # Size of BAAI/bge-small-en-v1.5 embeddings
        
        # Select client storage mode based on configuration settings
        if settings.QDRANT_URL == "in-memory" or os.getenv("TESTING") == "true":
            self.client = QdrantClient(location=":memory:")
            self.is_test = True
        else:
            self.client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY
            )
            self.is_test = False
            
        self._model = None

    def _get_embedding(self, text: str) -> List[float]:
        """Generate vector embedding (384 floats) for a text string."""
        if self.is_test or settings.QDRANT_URL == "in-memory":
            # Semantic mock embedding based on bag-of-words token overlap
            words = {
                "security": 0, "injection": 1, "sql": 2, "owasp": 3,
                "solid": 10, "single": 11, "responsibility": 12, "interface": 13,
                "bug": 20, "exception": 21, "error": 22, "clean": 23,
                "performance": 30, "loop": 31, "io": 32, "query": 33,
                "test": 40, "coverage": 41, "unit": 42
            }
            # Start with base hash noise
            h = hashlib.sha256(text.encode("utf-8")).digest()
            floats = []
            for i in range(self.vector_size):
                byte_val = h[(i * 7) % len(h)]
                floats.append(float(byte_val) / 500.0 - 0.25)
                
            # Insert high keyword weights to simulate semantic distance matching
            clean_text = text.lower()
            for word, index in words.items():
                if word in clean_text:
                    floats[index] = 1.0
                    
            # Normalize vector to unit length
            import math
            norm = math.sqrt(sum(x*x for x in floats))
            if norm > 0:
                floats = [x / norm for x in floats]
            return floats
            
        # Lazy load SentenceTransformer model in production
        if not self._model:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("BAAI/bge-small-en-v1.5")
            
        embedding_array = self._model.encode(text)
        return embedding_array.tolist()

    def init_collection(self):
        """Create the guidelines collection in Qdrant if it does not exist."""
        collections_response = self.client.get_collections()
        collection_names = [col.name for col in collections_response.collections]
        
        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.vector_size,
                    distance=qmodels.Distance.COSINE
                )
            )

    async def seed_guidelines(self, db: AsyncSession):
        """Parse local guidelines.json and insert records into Qdrant and Postgres."""
        self.init_collection()
        
        # Load local guidelines file
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, "resources", "guidelines.json")
        
        if not os.path.exists(file_path):
            return
            
        with open(file_path, "r", encoding="utf-8") as f:
            guidelines = json.load(f)
            
        for rule in guidelines:
            file_name = rule["file_name"]
            
            # Check if this rule is already indexed in Postgres
            stmt = select(RAGDocument).where(RAGDocument.file_name == file_name)
            res = await db.execute(stmt)
            existing_doc = res.scalar_one_or_none()
            
            if not existing_doc:
                text_content = rule["text_content"]
                rule_category = rule["rule_category"]
                
                # 1. Embed text
                vector = self._get_embedding(text_content)
                point_id = str(uuid.uuid4())
                
                # 2. Upload to Qdrant
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=[
                        qmodels.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload={
                                "file_name": file_name,
                                "rule_category": rule_category,
                                "text_content": text_content
                            }
                        )
                    ]
                )
                
                # 3. Save to Postgres
                new_doc = RAGDocument(
                    file_name=file_name,
                    rule_category=rule_category,
                    text_content=text_content,
                    qdrant_point_id=point_id
                )
                db.add(new_doc)
                
        await db.commit()

    async def retrieve_relevant_guidelines(self, diff_text: str, limit: int = 3) -> List[str]:
        """Query Qdrant for guidelines semantically similar to a pull request diff chunk."""
        # Ensure collection exists
        self.init_collection()
        
        # Embed PR diff chunk query
        query_vector = self._get_embedding(diff_text)
        
        try:
            res = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit
            )
            return [point.payload.get("text_content", "") for point in res.points if point.payload]
        except Exception as e:
            import sys
            sys.stderr.write(f"Qdrant retrieval error: {str(e)}\n")
            sys.stderr.flush()
            # Fallback in case of Qdrant connection errors
            return []

rag_service = RAGService()
