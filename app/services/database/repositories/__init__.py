"""Repository pattern for data access."""

from app.services.database.repositories.conversation import ConversationRepository
from app.services.database.repositories.feedback import FeedbackRepository
from app.services.database.repositories.popular import PopularRepository

__all__ = ["ConversationRepository", "FeedbackRepository", "PopularRepository"]
