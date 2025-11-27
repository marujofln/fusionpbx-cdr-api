"""CDR service for database operations."""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.cdr import CDR
from app.schemas.cdr import CDRResponse


class CDRService:
    """Service for CDR operations."""

    @staticmethod
    def get_cdrs_by_period(
        db: Session, domain: str, period: Optional[str] = None
    ) -> List[CDR]:
        """Get CDRs by time period."""
        now = datetime.utcnow()
        
        if period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif period == "yesterday":
            start_date = (now - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_date = start_date + timedelta(days=1)
        elif period == "last_7_days":
            start_date = now - timedelta(days=7)
            end_date = now
        elif period == "last_30_days":
            start_date = now - timedelta(days=30)
            end_date = now
        elif period == "this_week":
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=7)
        elif period == "this_month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = (start_date + timedelta(days=32)).replace(day=1)
        elif period == "this_year":
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date.replace(year=start_date.year + 1)
        else:
            # Default: last hour
            start_date = now - timedelta(hours=1)
            end_date = now

        return db.query(CDR).filter(
            and_(
                CDR.domain_name == domain,
                CDR.start_stamp >= start_date,
                CDR.start_stamp < end_date
            )
        ).order_by(CDR.start_stamp.desc()).all()

    @staticmethod
    def get_cdrs_by_date_range(
        db: Session, domain: str, start_date: datetime, end_date: datetime
    ) -> List[CDR]:
        """Get CDRs by custom date range."""
        return db.query(CDR).filter(
            and_(
                CDR.domain_name == domain,
                CDR.start_stamp >= start_date,
                CDR.start_stamp <= end_date
            )
        ).order_by(CDR.start_stamp.desc()).all()

    @staticmethod
    def get_cdr_count(db: Session, domain: str) -> int:
        """Get total CDR count for domain."""
        return db.query(func.count(CDR.xml_cdr_uuid)).filter(CDR.domain_name == domain).scalar()



