"""Database models for Motivora Studio."""

from datetime import datetime
from typing import Optional
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User account model."""
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # Nullable for OAuth users
    name = db.Column(db.String(255), nullable=False)
    google_id = db.Column(db.String(255), unique=True, nullable=True, index=True)  # Google OAuth ID
    subscription_tier = db.Column(db.String(50), default="free", nullable=False)  # free, pro, enterprise
    subscription_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    renders = db.relationship("Render", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")
    
    def set_password(self, password: str) -> None:
        """Hash and set password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """Check password against hash."""
        if not self.password_hash:
            return False  # OAuth users don't have passwords
        return check_password_hash(self.password_hash, password)
    
    @property
    def render_count_this_month(self) -> int:
        """Get count of renders this month."""
        from datetime import datetime, timedelta
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.renders.filter(Render.created_at >= start_of_month).count()
    
    @property
    def can_render(self) -> bool:
        """Check if user can render - unlimited renders for all tiers."""
        return True
    
    @property
    def can_download(self) -> bool:
        """Check if user can download renders - only pro/enterprise can download."""
        return self.subscription_tier in ("pro", "enterprise")
    
    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Render(db.Model):
    """Render job model."""
    __tablename__ = "renders"
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)  # Nullable for anonymous renders
    filename = db.Column(db.String(255), nullable=False)
    download_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)  # Path to rendered video
    file_size = db.Column(db.Integer, nullable=True)  # Size in bytes
    mimetype = db.Column(db.String(100), nullable=False)
    
    # Render settings
    quality = db.Column(db.String(50), nullable=False)
    video_format = db.Column(db.String(10), nullable=False)
    render_size = db.Column(db.Integer, nullable=False)
    axis = db.Column(db.String(1), nullable=False)
    offset = db.Column(db.Float, default=0.0)
    auto_orientation = db.Column(db.Boolean, default=False)
    
    # Status
    state = db.Column(db.String(50), default="running", nullable=False)  # running, finished, error, cancelled
    progress = db.Column(db.Float, default=0.0)
    message = db.Column(db.String(500), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship("User", back_populates="renders")
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate render duration in seconds."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
    
    def __repr__(self) -> str:
        return f"<Render {self.job_id} ({self.state})>"

