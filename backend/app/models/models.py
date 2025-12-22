from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, DateTime, Float, Boolean, Enum as SqEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from ..db import Base

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    s3_key = Column(String)
    duration = Column(Float)
    status = Column(SqEnum(JobStatus), default=JobStatus.PENDING)
    processing_stage = Column(String, default="")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Analysis capabilities
    has_audio = Column(Boolean, default=True)
    detected_systems = Column(JSON, default={}) # list of detected system names
    
    # Raw Extraction Data (Catalog)
    transcription_log = Column(JSON, default=[]) # Full aligned ASR data
    ocr_log = Column(JSON, default=[]) # Full raw OCR events

    flows = relationship("ProcessFlow", back_populates="video")

class ApprovalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"

class ProcessFlow(Base):
    __tablename__ = "process_flows"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"))
    title = Column(String)
    description = Column(Text, nullable=True)
    
    # Approval Workflow
    approval_status = Column(SqEnum(ApprovalStatus), default=ApprovalStatus.DRAFT)
    
    # JSON structure for the entire flow (nodes, edges) for BPMN/Mermaid
    graph_data = Column(JSON, default={})
    
    # Enterprise Feature: Spark Notes Summary
    summary_video_path = Column(String, nullable=True)
    removal_summary = Column(Text, nullable=True) # e.g. "Removed 45s of silence"
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="flows")
    steps = relationship("TrainingStep", back_populates="flow")
    wo_guides = relationship("WOGuide", back_populates="flow")

class TrainingStep(Base):
    __tablename__ = "training_steps"

    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, ForeignKey("process_flows.id"))
    step_number = Column(Integer, index=True)
    
    system_name = Column(String)
    action_type = Column(String) # click, type, navigate
    action_details = Column(Text)
    
    expected_result = Column(Text)
    notes = Column(Text)
    
    start_ts = Column(Float)
    end_ts = Column(Float)
    duration = Column(Float)
    
    screenshot_path = Column(String)
    video_clip_path = Column(String)
    
    ui_metadata = Column(JSON) # coordinates, validation rules
    
    # FR-7: Advanced Logic
    step_type = Column(String, default="linear") # linear, decision, loop_start, loop_end
    decision_map = Column(JSON, default={}) # {"Yes": next_step_id, "No": other_step_id}
    
    # FR-10: Prerequisites
    prerequisites = Column(JSON, default=[]) # List of required conditions/roles
    
    flow = relationship("ProcessFlow", back_populates="steps")

class WOGuide(Base):
    __tablename__ = "wo_guides"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, ForeignKey("process_flows.id"))
    title = Column(String)
    
    # Cross-System Mapping logic
    mapping_data = Column(JSON) # Tables defining Source -> Target field mappings
    sla_info = Column(Text)
    
    flow = relationship("ProcessFlow", back_populates="wo_guides")

class FlowVersion(Base):
    __tablename__ = "flow_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, ForeignKey("process_flows.id"))
    version_number = Column(Integer)
    graph_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    flow = relationship("ProcessFlow", back_populates="versions")

# Update ProcessFlow relationship
ProcessFlow.versions = relationship("FlowVersion", back_populates="flow", order_by="FlowVersion.version_number.desc()")

class GlossaryEntry(Base):
    __tablename__ = "glossary_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    error_keyword = Column(String, unique=True, index=True)
    resolution_text = Column(Text)
    confidence_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
