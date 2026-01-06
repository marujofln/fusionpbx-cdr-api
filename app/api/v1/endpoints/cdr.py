"""CDR endpoints."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_user_domain
from app.database.session import get_db
from app.schemas.cdr import CDRCompatResponse, CDRListResponse, CDRResponse
from app.services.cdr_service import CDRService

router = APIRouter()


@router.get("/cdr", response_model=CDRListResponse)
async def get_cdrs(
    request: Request,
    period: Optional[str] = Query(
        None,
        description="Time period filter",
        enum=[
            "today",
            "yesterday",
            "last_7_days",
            "last_30_days",
            "this_week",
            "this_month",
            "this_year",
        ],
    ),
    start_date: Optional[datetime] = Query(
        None, description="Start date for custom period"
    ),
    end_date: Optional[datetime] = Query(
        None, description="End date for custom period"
    ),
    domain: str = Depends(get_user_domain),
    db: AsyncSession = Depends(get_db),
) -> CDRListResponse:
    """Get call detail records for the authenticated user's domain."""

    if start_date and end_date:
        # Custom date range
        cdrs = await CDRService.get_cdrs_by_date_range(db, domain, start_date, end_date)
        period_str = f"custom_range_{start_date.date()}_to_{end_date.date()}"
    else:
        # Predefined period
        cdrs = await CDRService.get_cdrs_by_period(db, domain, period)
        period_str = period or "last_hour"

    # Get server URI from settings or extract from request
    server_uri = settings.app_server_uri
    if server_uri is None:
        # Extract base URL from request
        scheme = request.url.scheme
        hostname = request.url.hostname
        port = request.url.port

        # Construct base URL
        if port is None:
            # Default ports - don't include in URL
            server_uri = f"{scheme}://{hostname}"
        else:
            # Include port in URL for non-standard ports
            server_uri = f"{scheme}://{hostname}:{port}"

    # Build CDRResponse objects with recording URLs
    cdr_responses = []
    for cdr in cdrs:
        cdr_response = CDRResponse.model_validate(cdr)
        
        # Construct recording URL from record_path and record_name, removing recording_path_prefix
        recording_url = None
        if cdr.record_path:
            # Normalize the recording path prefix for comparison
            record_path = cdr.record_path
            if settings.fusionpbx_recording_path:
                # Normalize both paths (remove trailing/leading slashes for comparison)
                prefix_normalized = settings.fusionpbx_recording_path.rstrip('/')
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
                    recording_url = f"{record_path}/{record_name}"
                else:
                    recording_url = f"{record_path}{record_name}"
            else:
                recording_url = record_path
        elif cdr.record_name:
            record_name = cdr.record_name
            recording_url = record_name
        
        # Prepend server_uri/v1/recording/ if server_uri is provided
        if server_uri and recording_url:
            # Normalize server_uri (remove trailing slash)
            server_uri_normalized = server_uri.rstrip('/')
            # Ensure recording_url doesn't have leading slash (we'll add it)
            recording_url_normalized = recording_url.lstrip('/')
            recording_url = f"{server_uri_normalized}/v1/recording/{recording_url_normalized}"
        
        cdr_response.recording = recording_url
        cdr_responses.append(cdr_response)

    return CDRListResponse(
        cdrs=cdr_responses,
        total=len(cdr_responses),
        period=period_str,
    )


@router.get("/cdr_compat", response_model=List[CDRCompatResponse])
async def get_cdrs_compat(
    request: Request,
    period: Optional[str] = Query(
        None,
        description="Time period filter",
        enum=[
            "today",
            "yesterday",
            "last_7_days",
            "last_30_days",
            "this_week",
            "this_month",
            "this_year",
        ],
    ),
    start_date: Optional[datetime] = Query(
        None, description="Start date for custom period"
    ),
    end_date: Optional[datetime] = Query(
        None, description="End date for custom period"
    ),
    domain: str = Depends(get_user_domain),
    db: AsyncSession = Depends(get_db),
) -> List[CDRCompatResponse]:
    """Get call detail records in legacy-compatible format for the authenticated user's domain."""

    if start_date and end_date:
        # Custom date range
        cdrs = await CDRService.get_cdrs_by_date_range(db, domain, start_date, end_date)
    else:
        # Predefined period
        cdrs = await CDRService.get_cdrs_by_period(db, domain, period)

    # Get server URI from settings or extract from request
    server_uri = settings.app_server_uri
    if server_uri is None:
        # Extract base URL from request
        scheme = request.url.scheme
        hostname = request.url.hostname
        port = request.url.port

        # Construct base URL
        if port is None:
            # Default ports - don't include in URL
            server_uri = f"{scheme}://{hostname}"
        else:
            # Include port in URL for non-standard ports
            server_uri = f"{scheme}://{hostname}:{port}"

    return [
        CDRCompatResponse.from_cdr(cdr, settings.fusionpbx_recording_path, server_uri)
        for cdr in cdrs
    ]
