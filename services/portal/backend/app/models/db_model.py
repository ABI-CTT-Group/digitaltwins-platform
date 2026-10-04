import os
import re
import uuid
from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, Text, JSON, Boolean, Enum, Table, Integer, CheckConstraint
from sqlalchemy.engine import URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from pydantic import BaseModel, model_validator
from enum import Enum as PyEnum
from datetime import datetime
from typing import Optional, Literal, List, Any

# Under the platform the tables live in this schema of the shared Postgres; it is
# selected via search_path so the models stay schema-agnostic (and SQLite-compatible).
PORTAL_DB_SCHEMA = "portal"

# A deployment runs the backend of either a tool build or a gui workflow's build, never both.
DEPLOYMENT_ONE_BUILD = "ck_plugin_deployments_one_build"


def database_url() -> URL:
    """Postgres from the PORTAL_DB_* variables when PORTAL_DB_HOST is set, else SQLite at DATABASE_PATH."""
    if not os.getenv("PORTAL_DB_HOST"):
        return URL.create("sqlite", database=os.getenv("DATABASE_PATH", "./plugin_registry.db"))
    return URL.create(
        "postgresql+psycopg2",
        host=os.environ["PORTAL_DB_HOST"],
        port=int(os.getenv("PORTAL_DB_PORT", "5432")),
        database=os.getenv("PORTAL_DB_NAME", "digitaltwins"),
        username=os.getenv("PORTAL_DB_USER", "portal"),
        password=os.getenv("PORTAL_DB_PASSWORD"),
    )


def _build_engine():
    url = database_url()
    if url.drivername == "sqlite":
        return create_engine(url, connect_args={'check_same_thread': False})
    return create_engine(url, pool_pre_ping=True, connect_args={"options": f"-csearch_path={PORTAL_DB_SCHEMA}"})


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class BuildStatus(PyEnum):
    PENDING = "pending"
    BUILDING = "building"
    FAILED = "failed"
    COMPLETED = "completed"


class DeployStatus(PyEnum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    FAILED = "failed"
    COMPLETED = "completed"


# A GUI tool's frontend build command (tools and gui workflows): only npm or yarn runs on the portal.
DEFAULT_GUI_BUILD_COMMAND = "npm run build:plugin"
GUI_BUILD_COMMAND = re.compile(r"^(npm|yarn)\s+\S+")

workflow_plugin_association = Table(
    "workflow_plugin_association",
    Base.metadata,
    Column("workflow_id", String, ForeignKey("workflows.id", ondelete="CASCADE")),
    Column("plugin_id", String, ForeignKey("plugins.id", ondelete="CASCADE")),
)

class Plugin(Base):
    __tablename__ = "plugins"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    uuid = Column(String, unique=True, nullable=True)
    name = Column(String, index=True, nullable=False)
    version = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    author = Column(String, nullable=True)
    repository_url = Column(String, nullable=False)
    source_type = Column(String, nullable=False, default="github")
    local_archive_path = Column(String, nullable=True)
    plugin_metadata = Column(JSON, nullable=True)
    label = Column(Enum("GUI", "Script", "Notebook", name="plugin_label"), nullable=False)
    has_backend = Column(Boolean, nullable=False, default=True)
    frontend_folder = Column(String, nullable=False)
    frontend_build_command = Column(String, nullable=False)
    backend_folder = Column(String, nullable=True)
    backend_deploy_command = Column(String, nullable=True, default="docker compose up --build -d")
    # SEEK project the tool is registered in on approval (kept as the default for re-approval).
    seek_project_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workflows = relationship(
        "Workflow",
        secondary=workflow_plugin_association,
        back_populates="plugins",
    )
    builds = relationship("PluginBuild", back_populates="plugin", cascade="all, delete-orphan")
    deployments = relationship("PluginDeployment", back_populates="plugin", cascade="all, delete-orphan")
    annotation = relationship("PluginAnnotation", back_populates="plugin", uselist=False, cascade="all, delete-orphan")


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
    # Approval hands the build to digitaltwins-api (app/services/tool_handoff.py).
    handoff_status = Column(String, nullable=True)  # uploading|awaiting_reauth|committing|completed|failed
    upload_id = Column(String, nullable=True)       # the API's upload session
    dataset_uuid = Column(String, nullable=True)    # the platform dataset, once committed
    seek_id = Column(String, nullable=True)
    handoff_error = Column(Text, nullable=True)
    handoff_user = Column(String, nullable=True)    # the approver; only their token may continue the handoff
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plugin = relationship("Plugin", back_populates="builds")
    deployments = relationship("PluginDeployment", back_populates="build", cascade="all, delete-orphan")


class PluginDeployment(Base):
    __tablename__ = "plugin_deployments"
    __table_args__ = (CheckConstraint("(build_id IS NULL) <> (workflow_build_id IS NULL)", name=DEPLOYMENT_ONE_BUILD),)
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String, ForeignKey("plugins.id"), nullable=True)  # null for a gui workflow's tool
    # References the build's business key (what the deploy endpoint stores), not plugin_builds.id.
    build_id = Column(String, ForeignKey("plugin_builds.build_id"), nullable=True)
    workflow_build_id = Column(String, ForeignKey("workflow_builds.build_id"), nullable=True)
    deploy_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default=DeployStatus.PENDING.value, nullable=False)
    source_path = Column(String, nullable=True)
    up = Column(Boolean, default=False, nullable=True)
    # Nginx routing metadata
    route_prefix = Column(String, nullable=True)       # e.g. /plugin/annotator
    internal_host = Column(String, nullable=True)       # Docker container name, e.g. annotator-backend
    internal_port = Column(String, nullable=True)       # Container internal port, e.g. 8082
    has_websocket = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    build = relationship("PluginBuild", back_populates="deployments")
    plugin = relationship("Plugin", back_populates="deployments")
    workflow_build = relationship("WorkflowBuild", back_populates="deployments")


class PluginAnnotation(Base):
    __tablename__ = "plugin_annotations"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    plugin_id = Column(String, ForeignKey("plugins.id"), nullable=False)
    annotation_id = Column(String, unique=True, index=True, nullable=False)
    sparc_note = Column(String, nullable=True)
    fhir_note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plugin = relationship("Plugin", back_populates="annotation", uselist=False)


class Workflow(Base):
    __tablename__ = "workflows"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    uuid = Column(String, unique=True, nullable=True)
    name = Column(String, index=True, nullable=False)
    version = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    author = Column(String, nullable=True)
    repository_url = Column(String, nullable=False)
    source_type = Column(String, nullable=False, default="github")
    local_archive_path = Column(String, nullable=True)
    workflow_type = Column(String, nullable=True)  # script|notebook|gui; NULL on rows registered before 2026-10-02
    # Set by a successful build from the source layout (app/builder/workflow_layout.py); NULL until built.
    # An SDS package is approved through digitaltwins-api (see docs/decisions/2026-10-02-workflow-type-independent-of-sds.md).
    is_sds = Column(Boolean, nullable=True)
    seek_project_id = Column(Integer, nullable=True)
    # A gui SDS workflow builds its tool's frontend like a GUI tool (Plugin); folders are relative to code/.
    has_backend = Column(Boolean, nullable=True, default=False)
    frontend_folder = Column(String, nullable=True)
    frontend_build_command = Column(String, nullable=True)
    backend_folder = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plugins = relationship(
        "Plugin",
        secondary=workflow_plugin_association,
        back_populates="workflows",
    )
    builds = relationship("WorkflowBuild", back_populates="workflow", cascade="all, delete-orphan")
    annotation = relationship("WorkflowAnnotation", back_populates="workflow", uselist=False,
                              cascade="all, delete-orphan")


class WorkflowBuild(Base):
    __tablename__ = "workflow_builds"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, ForeignKey("workflows.id"), nullable=False)
    build_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default=BuildStatus.PENDING.value, nullable=False)
    build_logs = Column(Text, nullable=True)
    error_messages = Column(Text, nullable=True)
    s3_path = Column(String, nullable=True)
    expose_name = Column(String, nullable=True)
    dataset_path = Column(String, nullable=True)
    # Approval hands the build to digitaltwins-api (app/services/workflow_handoff.py).
    handoff_status = Column(String, nullable=True)  # uploading|awaiting_reauth|committing|completed|failed
    upload_id = Column(String, nullable=True)       # the API's upload session
    dataset_uuid = Column(String, nullable=True)    # the platform dataset, once committed
    seek_id = Column(String, nullable=True)
    handoff_error = Column(Text, nullable=True)
    handoff_user = Column(String, nullable=True)    # the approver; only their token may continue the handoff
    # A gui SDS workflow's built tool (app/builder/build_workflow.py): its CWL stem (set only when the bundle
    # was built), the bundle's tool-builds prefix (null if that upload failed) and, once approved, its tool dataset.
    tool_name = Column(String, nullable=True)
    bundle_path = Column(String, nullable=True)        # e.g. tool-builds/<expose>/primary
    tool_dataset_uuid = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workflow = relationship("Workflow", back_populates="builds")
    deployments = relationship("PluginDeployment", back_populates="workflow_build", cascade="all, delete-orphan")


class WorkflowAnnotation(Base):
    __tablename__ = "workflow_annotations"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, ForeignKey("workflows.id"), nullable=False)
    annotation_id = Column(String, unique=True, index=True, nullable=False)
    fhir_note = Column(String, nullable=True)
    sparc_note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workflow = relationship("Workflow", back_populates="annotation", uselist=False)


class PluginBase(BaseModel):
    name: str
    version: str
    repository_url: Optional[str] = None
    source_type: Literal["github", "gitlab", "bitbucket", "git_generic", "local"] = "github"
    frontend_folder: str
    frontend_build_command: str
    label: Literal["GUI", "Script", "Notebook"]
    has_backend: bool
    backend_folder: Optional[str]
    backend_deploy_command: str
    description: Optional[str] = None
    author: Optional[str] = None
    plugin_metadata: Optional[dict] = None


class PluginCreate(PluginBase):
    upload_id: Optional[str] = None  # client-supplied at create-time only; resolved to local_archive_path server-side


class PluginUpdate(PluginBase):
    name: Optional[str] = None
    version: Optional[str] = None
    plugin_metadata: Optional[dict] = None


class PluginResponse(PluginBase):
    id: str
    uuid: Optional[str] = None
    seek_project_id: Optional[int] = None
    plugin_metadata: Optional[dict] = None
    workflow_ids: Optional[List[str]] = None
    local_archive_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BuildBase(BaseModel):
    build_id: Optional[str] = None
    status: Optional[str] = BuildStatus.PENDING.value
    build_logs: Optional[str] = None
    error_messages: Optional[str] = None
    s3_path: Optional[str] = None


class BuildUpdate(BaseModel):
    status: Optional[str] = None
    build_logs: Optional[str] = None
    error_messages: Optional[str] = None
    s3_path: Optional[str] = None


class PluginBuildResponse(BuildBase):
    id: str
    plugin_id: str
    build_id: str
    status: str
    expose_name: Optional[str] = None
    handoff_status: Optional[str] = None
    dataset_uuid: Optional[str] = None
    seek_id: Optional[str] = None
    handoff_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PluginDeployBase(BaseModel):
    deploy_id: Optional[str] = None
    status: Optional[str] = BuildStatus.PENDING.value
    error_messages: Optional[str] = None


class PluginDeployResponse(PluginDeployBase):
    id: str
    plugin_id: Optional[str] = None
    build_id: Optional[str] = None
    workflow_build_id: Optional[str] = None
    deploy_id: str
    status: str
    up: bool
    route_prefix: Optional[str] = None
    internal_host: Optional[str] = None
    internal_port: Optional[str] = None
    has_websocket: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnnotationBase(BaseModel):
    fhir_note: Optional[str] = None
    sparc_note: Optional[str] = None


class PluginAnnotationCreate(AnnotationBase):
    pass


class PluginAnnotationResponse(AnnotationBase):
    id: str
    annotation_id: str
    fhir_note: str
    sparc_note: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowBase(BaseModel):
    name: str
    version: str
    repository_url: Optional[str] = None
    source_type: Literal["github", "gitlab", "bitbucket", "git_generic", "local"] = "github"
    description: Optional[str] = None
    author: Optional[str] = None
    workflow_type: Optional[Literal["script", "notebook", "gui"]] = None
    # gui SDS workflows only (see Workflow): how to build the tool's frontend, as for GUI tools.
    has_backend: Optional[bool] = False
    frontend_folder: Optional[str] = None
    frontend_build_command: Optional[str] = None
    backend_folder: Optional[str] = None


# --- Source-acquisition request bodies (phase 5: multi-git-provider) ---
#
# Token / auth_username / verify_ssl are TRANSIENT — accepted at request
# boundary and passed through to the acquirer in-process. Never persisted.

class ProbeSourceRequest(BaseModel):
    """POST body for `/probe-source`. Local-upload sources have their own
    `/upload-source` endpoint, so this Literal deliberately excludes ``local``.
    """
    source_type: Literal["github", "gitlab", "bitbucket", "git_generic"]
    url: str
    branch: str = "main"
    token: Optional[str] = None
    auth_username: Optional[str] = None
    verify_ssl: bool = True


class BuildTriggerRequest(BaseModel):
    """Optional transient secrets for triggering a build.

    All fields optional — public-source plugins/workflows just POST ``{}``.
    Private-source builds supply the token (and ``auth_username`` for
    generic git, ``verify_ssl=false`` for self-signed certs). NEVER stored;
    user must re-supply for every rebuild.
    """
    token: Optional[str] = None
    auth_username: Optional[str] = None
    verify_ssl: bool = True


class ProbeSourceFailure(BaseModel):
    """Structured failure response shape — frontend dispatches off ``reason``
    to decide which UI fields to expand (token / auth_username / SSL toggle).

    HTTP status is 200 even on failure: the probe operation completed, the
    structured payload is the answer. Frontend reads ``ok`` to branch.
    """
    ok: bool = False
    reason: str
    message: str
    provider_hint: Optional[str] = None


class WorkflowCreate(WorkflowBase):
    workflow_type: Literal["script", "notebook", "gui"]  # required for new workflows; optional on WorkflowBase for older rows
    upload_id: Optional[str] = None  # client-supplied at create-time only; resolved to local_archive_path server-side

    @model_validator(mode="after")
    def _gui_fields(self):
        """Only a gui workflow keeps a frontend layout; a backend needs both folders (relative to code/)."""
        if self.workflow_type != "gui":
            self.has_backend, self.frontend_folder, self.frontend_build_command, self.backend_folder = False, None, None, None
            return self
        self.has_backend = bool(self.has_backend)
        self.frontend_build_command = self.frontend_build_command or DEFAULT_GUI_BUILD_COMMAND
        if not GUI_BUILD_COMMAND.match(self.frontend_build_command):
            raise ValueError("frontend_build_command must be an npm or yarn command, e.g. npm run build:plugin")
        if self.has_backend and not (self.frontend_folder and self.backend_folder):
            raise ValueError("A gui workflow with a backend needs frontend_folder and backend_folder")
        if self.has_backend:
            for folder in (self.frontend_folder, self.backend_folder):
                if "/" in folder or "\\" in folder or folder in (".", ".."):
                    raise ValueError("frontend_folder and backend_folder must be folder names inside code/")
        else:
            self.frontend_folder = self.backend_folder = None
        return self


class WorkflowResponse(WorkflowBase):
    id: str
    uuid: Optional[str] = None
    local_archive_path: Optional[str] = None
    seek_project_id: Optional[int] = None
    is_sds: Optional[bool] = None  # set by the build; never accepted from the client
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowBuildResponse(BuildBase):
    id: str
    workflow_id: str
    build_id: str
    status: str
    expose_name: Optional[str] = None
    handoff_status: Optional[str] = None
    dataset_uuid: Optional[str] = None
    seek_id: Optional[str] = None
    handoff_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowAnnotationCreate(AnnotationBase):
    pass


class WorkflowAnnotationResponse(AnnotationBase):
    id: str
    annotation_id: str
    fhir_note: str
    sparc_note: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
