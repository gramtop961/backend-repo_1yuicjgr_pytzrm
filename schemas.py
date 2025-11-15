"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class Settings(BaseModel):
    """
    App-level settings for a single user (owner)
    Collection: settings
    """
    owner_id: str = Field("owner", description="Singleton identifier")
    gmail_email: Optional[str] = Field(None, description="Gmail address used for IMAP/SMTP")
    gmail_app_password: Optional[str] = Field(None, description="Gmail app password for IMAP/SMTP (use app-specific password)")
    keywords: List[str] = Field(default_factory=lambda: ["psych", "psychology", "mental health", "therapy", "behavioral"], description="Keywords used to detect relevant queries")
    tone: Literal["formal", "friendly", "confident", "concise"] = Field("friendly", description="Tone for generated pitches")
    voice: str = Field("First-person expert but approachable", description="Voice guidance for the pitch generator")
    style_notes: Optional[str] = Field(None, description="Additional style notes / rules")
    intro_template: str = Field(
        default="Hi {name},\n\nThanks for reaching out. I'm {your_name}, a {your_title}.",
        description="Intro line template with placeholders: {name}, {your_name}, {your_title}"
    )
    signature_template: str = Field(
        default="\n\nBest,\n{your_name}\n{your_title}\n{your_website}",
        description="Signature template with placeholders: {your_name}, {your_title}, {your_website}"
    )
    your_name: Optional[str] = Field(None, description="Displayed name in emails")
    your_title: Optional[str] = Field(None, description="Displayed title in emails")
    your_website: Optional[str] = Field(None, description="Website or portfolio link")


class Query(BaseModel):
    """
    A single newsletter query detected from Gmail
    Collection: query
    """
    subject: str
    sender_email: str
    sender_name: Optional[str] = None
    received_at: datetime
    deadline: Optional[datetime] = None
    body_text: str
    source_message_id: Optional[str] = Field(None, description="Gmail message-id or uid for reference")
    status: Literal["new", "drafted", "approved", "sent", "ignored"] = Field("new")
    tags: List[str] = Field(default_factory=list)


class Pitch(BaseModel):
    """
    Generated pitch content for a query
    Collection: pitch
    """
    query_id: str
    content: str
    style_used: dict
    created_at: datetime


class EmailDraft(BaseModel):
    """
    Drafted email based on a pitch
    Collection: emaildraft
    """
    query_id: str
    to_email: str
    subject: str
    body: str
    approved: bool = False
    created_at: datetime

