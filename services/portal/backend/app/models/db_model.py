import os
import uuid
from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from typing import Optional

DATABASE_PATH = os.getenv("DATABASE_PATH", "./plugin_registry.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class BuildStatus(Enum):
    PENDING = "pending"
    BUILDING = "building"
    FAILED = "failed"
    COMPLETED = "completed"


class Plugin(Base):
    __tablename__ = "plugins"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, index=True, nullable=False)
    version = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    author = Column(String, nullable=True)
    repository_url = Column(String, nullable=False)
    plugin_metadata = Column(JSON, nullable=True)
    has_backend = Column(Boolean, nullable=False, default=True)
    frontend_folder = Column(String, nullable=False)
    frontend_build_command = Column(String, nullable=False)
    backend_folder = Column(String, nullable=True)
    backend_deploy_command = Column(String, nullable=True, default="docker compose up --build -d")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    builds = relationship("PluginBuild", back_populates="plugin", cascade="all, delete-orphan")


class PluginBuild(Base):
    __tablename__ = "plugin_builds"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String, ForeignKey("plugins.id"), nullable=False)
    build_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default=BuildStatus.PENDING.value, nullable=False)
    build_logs = Column(Text, nullable=True)
    error_messages = Column(Text, nullable=True)
    s3_path = Column(String, nullable=True)
    expose_name = Column(String, nullable=True)
    dataset_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plugin = relationship("Plugin", back_populates="builds")


class PluginBase(BaseModel):
    name: str
    version: str
    repository_url: str
    frontend_folder: str
    frontend_build_command: str
    has_backend: bool
    backend_folder: Optional[str]
    backend_deploy_command: str
    description: Optional[str] = None
    author: Optional[str] = None
    plugin_metadata: Optional[dict] = None


class PluginCreate(PluginBase):
    pass


class PluginUpdate(PluginBase):
    name: Optional[str] = None
    version: Optional[str] = None
    plugin_metadata: Optional[dict] = None


class PluginResponse(PluginBase):
    id: str
    plugin_metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PluginBuildBase(BaseModel):
    build_id: Optional[str] = None
    status: Optional[str] = BuildStatus.PENDING.value
    build_logs: Optional[str] = None
    error_messages: Optional[str] = None
    s3_path: Optional[str] = None


class PluginBuildUpdate(BaseModel):
    status: Optional[str] = None
    build_logs: Optional[str] = None
    error_messages: Optional[str] = None
    s3_path: Optional[str] = None


class PluginBuildResponse(PluginBuildBase):
    id: str
    plugin_id: str
    build_id: str
    status: str
    expose_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
