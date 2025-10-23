from sqlalchemy import Column, Integer, Text, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from backend.database import Base

class UserComparison(Base):
    __tablename__ = "user_comparisons"

    comparison_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.route_id", ondelete="RESTRICT"), nullable=False)
    months_compared = Column(JSONB, nullable=False)
    notes = Column(Text)
    created_at = Column(TIMESTAMP, nullable=False)

    user = relationship("User", backref="comparisons")
    route = relationship("Route", backref="comparisons")
