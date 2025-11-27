"""CDR request and response schemas."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class CDRResponse(BaseModel):
    """CDR response model."""
    xml_cdr_uuid: str
    domain_name: Optional[str] = None
    accountcode: Optional[str] = None
    caller_id_name: Optional[str] = None
    caller_id_number: Optional[str] = None
    destination_number: Optional[str] = None
    context: Optional[str] = None
    start_stamp: Optional[datetime] = None
    answer_stamp: Optional[datetime] = None
    end_stamp: Optional[datetime] = None
    duration: Optional[float] = None
    billsec: Optional[float] = None
    hangup_cause: Optional[str] = None
    read_codec: Optional[str] = None
    write_codec: Optional[str] = None
    recording: Optional[str] = None

    class Config:
        """Pydantic configuration."""
        from_attributes = True


class CDRListResponse(BaseModel):
    """CDR list response model."""
    cdrs: List[CDRResponse]
    total: int
    period: str


class CDRCompatResponse(BaseModel):
    """CDR compatibility response model for legacy format."""
    date: str
    type: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    duration: str
    cost: str = "R$ 0.00"
    status: Optional[str] = None
    audio: Optional[str] = None

    @classmethod
    def from_cdr(
        cls,
        cdr,
        recording_path_prefix: Optional[str] = None,
        server_uri: Optional[str] = None,
    ):
        """Create CDRCompatResponse from CDR model instance.
        
        Args:
            cdr: CDR model instance
            recording_path_prefix: Prefix to remove from record_path (e.g., FUSIONPBX_RECORDING_PATH)
            server_uri: Server URI to prepend to audio URL (e.g., http://example.com)
        """
        # Format date as "DD/MM/YYYY HH:MM:SS"
        date_str = ""
        if cdr.start_stamp:
            date_str = cdr.start_stamp.strftime("%d/%m/%Y %H:%M:%S")
        
        # Format duration as "HH:MM:SS"
        duration_str = "00:00:00"
        if cdr.duration is not None:
            total_seconds = int(float(cdr.duration))
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Construct audio URL from record_path and record_name, removing recording_path_prefix
        audio_url = None
        if cdr.record_path:
            # Normalize the recording path prefix for comparison
            record_path = cdr.record_path
            if recording_path_prefix:
                # Normalize both paths (remove trailing/leading slashes for comparison)
                prefix_normalized = recording_path_prefix.rstrip('/')
                # Remove the prefix if record_path starts with it
                if record_path.startswith(prefix_normalized):
                    record_path = record_path[len(prefix_normalized):].lstrip('/')
                else:
                    # If prefix doesn't match, just remove leading slash
                    record_path = record_path.lstrip('/')
            else:
                record_path = record_path.lstrip('/')
            
            # Combine with record_name if it exists
            if cdr.record_name:
                record_name = cdr.record_name
                # Ensure proper slash between path and name if path doesn't end with one
                if record_path and not record_path.endswith('/'):
                    audio_url = f"{record_path}/{record_name}"
                else:
                    audio_url = f"{record_path}{record_name}"
            else:
                audio_url = record_path
        elif cdr.record_name:
            record_name = cdr.record_name
            audio_url = record_name
        
        # Prepend server_uri/v1/recording/ if server_uri is provided
        if server_uri and audio_url:
            # Normalize server_uri (remove trailing slash)
            server_uri_normalized = server_uri.rstrip('/')
            # Ensure audio_url doesn't have leading slash (we'll add it)
            audio_url_normalized = audio_url.lstrip('/')
            audio_url = f"{server_uri_normalized}/v1/recording/{audio_url_normalized}"
        
        return cls(
            date=date_str,
            type=cdr.direction,
            origin=cdr.caller_id_number,
            destination=cdr.destination_number,
            duration=duration_str,
            cost="R$ 0.00",
            status=cdr.hangup_cause,
            audio=audio_url
        )



