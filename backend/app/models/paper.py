import sqlalchemy as sa
from datetime import datetime
from app.database import Base


class Paper(Base):
    __tablename__ = "papers"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    arxiv_id = sa.Column(sa.String, unique=True, nullable=False, index=True)
    title = sa.Column(sa.String, nullable=False)
    abstract = sa.Column(sa.Text, nullable=False)
    authors = sa.Column(sa.Text, nullable=False)  # JSON list of author names
    categories = sa.Column(sa.String, nullable=False)  # comma-separated
    pdf_url = sa.Column(sa.String, nullable=False)
    arxiv_url = sa.Column(sa.String, nullable=False)
    published_date = sa.Column(sa.DateTime, nullable=False)
    scraped_date = sa.Column(sa.DateTime, default=datetime.utcnow)

    # LLM relevance scoring
    relevance_score = sa.Column(sa.Float, nullable=True)  # 0-1, how relevant
    relevance_reason = sa.Column(sa.Text, nullable=True)  # LLM explanation

    # Source tracking: 'arxiv', 'acm', 'scholar'
    source = sa.Column(sa.String, default="arxiv", nullable=True)

    # Artifact detection: GitHub/GitLab/Zenodo/HuggingFace links found in abstract
    has_artifacts = sa.Column(sa.Boolean, default=False, nullable=True)
    artifact_links = sa.Column(sa.Text, nullable=True)  # JSON list of URLs

    # User interaction
    # "pending" = not swiped, "liked" = right swipe, "passed" = left swipe
    status = sa.Column(sa.String, default="pending", index=True)
    swiped_at = sa.Column(sa.DateTime, nullable=True)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": json.loads(self.authors) if self.authors else [],
            "categories": self.categories,
            "pdf_url": self.pdf_url,
            "arxiv_url": self.arxiv_url,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "scraped_date": self.scraped_date.isoformat() if self.scraped_date else None,
            "relevance_score": self.relevance_score,
            "relevance_reason": self.relevance_reason,
            "source": self.source or "arxiv",
            "has_artifacts": bool(self.has_artifacts),
            "artifact_links": json.loads(self.artifact_links) if self.artifact_links else [],
            "status": self.status,
            "swiped_at": self.swiped_at.isoformat() if self.swiped_at else None,
        }


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    key = sa.Column(sa.String, unique=True, nullable=False)
    value = sa.Column(sa.Text, nullable=False)
    updated_at = sa.Column(sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FavoriteAuthor(Base):
    __tablename__ = "favorite_authors"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    name = sa.Column(sa.String, unique=True, nullable=False, index=True)
    added_at = sa.Column(sa.DateTime, default=datetime.utcnow)
