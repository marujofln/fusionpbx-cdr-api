"""CDR (Call Detail Record) model."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID

from app.database.session import Base


class CDR(Base):
    """Call Detail Record model."""
    __tablename__ = "v_xml_cdr"

    xml_cdr_uuid = Column(UUID(as_uuid=False), primary_key=True, index=True)
    domain_name = Column(Text, index=True)
    accountcode = Column(Text)
    caller_id_name = Column(Text)
    caller_id_number = Column(Text)
    destination_number = Column(Text)
    context = Column(Text)
    start_stamp = Column(DateTime(timezone=True), index=True)
    answer_stamp = Column(DateTime(timezone=True))
    end_stamp = Column(DateTime(timezone=True), index=True)
    duration = Column(Numeric)
    billsec = Column(Numeric)
    hangup_cause = Column(Text)
    read_codec = Column(Text)
    write_codec = Column(Text)
    direction = Column(Text)
    record_path = Column(Text)
    record_name = Column(Text)



