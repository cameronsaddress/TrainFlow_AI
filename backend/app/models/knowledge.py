from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum, Text, DateTime, JSON, Float
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid
import enum

from ..db import Base

class DocStatus(str, enum.Enum):
    PENDING = "PENDING"
    INDEXING = "INDEXING"
    READY = "READY"
    FAILED = "FAILED"

class RuleType(str, enum.Enum):
    FORMAT = "FORMAT"      # e.g., "Must match Regex"
    SEQUENCE = "SEQUENCE"  # e.g., "Step A must precede Step B"
    UNBLOCKER = "UNBLOCKER"# e.g., "Help Desk Number"
    COMPLIANCE = "COMPLIANCE" # e.g. "Must verify X"

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String) # MinIO path or local
    status = Column(Enum(DocStatus), default=DocStatus.PENDING)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")
    rules = relationship("BusinessRule", back_populates="document", cascade="all, delete-orphan")

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id"))
    content = Column(Text) # The actual text chunk
    embedding = Column(Vector(768)) # Using Gemini/OpenAI embedding dim (768 for Vertex, 1536 for OpenAI) - let's default to 768 or make it generic? 
    # NOTE: OpenAI text-embedding-3-small is 1536. Vertex is 768. 
    # Let's assume 1536 for broad compatibility if we swap, but we can change.
    # User env has OPENAI key, so likely 1536. BUT user also mentioned 'google/gemini-3-flash-preview'.
    # If using gemini for embeddings, it is 768. If using OpenAI, 1536.
    # Safe bet: 1536 covers OpenAI. If passing 768 to 1536 col, it works? No vector dims must match.
    # LLM Service seems to use OpenRouter. Let's fix this in Ingestor, but define col size here.
    # We will use 1536 (OpenAI Standard) for now.
    
    metadata_json = Column(JSON, default={}) # Page number, section header
    
    document = relationship("KnowledgeDocument", back_populates="chunks")

class BusinessRule(Base):
    __tablename__ = "business_rules"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id"))
    
    trigger_context = Column(String) # "Screen: Login", "Action: Submit"
    rule_description = Column(String) # "Must use format X"
    rule_type = Column(Enum(RuleType), default=RuleType.COMPLIANCE)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("KnowledgeDocument", back_populates="rules")

class VideoCorpus(Base):
    __tablename__ = "video_corpus"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    file_path = Column(String)
    transcript_text = Column(Text, nullable=True) # Full ASR (Text Blob)
    transcript_json = Column(JSON, nullable=True) # Rich Data: Timestamps, Speakers
    ocr_text = Column(Text, nullable=True)       # Aggregated OCR
    ocr_json = Column(JSON, nullable=True)       # Rich Data: Sampled Frames with Timestamps
    duration_seconds = Column(Float, nullable=True)
    status = Column(Enum(DocStatus), default=DocStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Metadata for potential future expansion (resolution, codec, etc)
    metadata_json = Column(JSON, nullable=True)

class TrainingCurriculum(Base):
    __tablename__ = "training_curricula"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    structured_json = Column(JSON) # The full course plan
    created_at = Column(DateTime, default=datetime.utcnow)
