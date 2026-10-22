"""Recording endpoints."""

import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def parse_range_header(range_header: Optional[str], file_size: int) -> Optional[Tuple[int, int]]:
    """
    Parse Range header and return (start, end) tuple.
    Returns None if range is invalid or not satisfiable.
    """
    if not range_header:
        return None
    
    if not range_header.startswith("bytes="):
        return None
    
    try:
        ranges = range_header[6:].split(",")
        if len(ranges) != 1:
            # Multiple ranges not supported, return None
            return None
        
        range_spec = ranges[0].strip()
        if "-" not in range_spec:
            return None
        
        start_str, end_str = range_spec.split("-", 1)
        
        if start_str:
            start = int(start_str)
        else:
            # Suffix range: last N bytes
            end = int(end_str)
            start = max(0, file_size - end)
            end = file_size - 1
            return (start, end)
        
        if end_str:
            end = int(end_str)
        else:
            # Start to end of file
            end = file_size - 1
        
        # Validate range
        if start < 0 or end >= file_size or start > end:
            return None
        
        return (start, end)
    except (ValueError, IndexError):
        return None


def generate_etag(file_path: Path, file_size: int, mtime: float) -> str:
    """Generate ETag from file metadata."""
    # Use file path, size, and modification time for ETag
    etag_data = f"{file_path}{file_size}{mtime}"
    return hashlib.md5(etag_data.encode()).hexdigest()


@router.get("/recording/{file_path:path}")
async def get_recording(
    file_path: str,
    request: Request,
) -> Response:
    """
    Get audio recording file from filesystem.

    The file_path parameter should be a relative path from the recording base path.
    Example: /v1/recording/example.com/archive/2025/Nov/24/file.mp3

    Note: This endpoint does not require authentication.
    Security: Path traversal protection ensures files can only be accessed within the base path.
    """
    try:
        # Get the recording base path
        if settings.app_recording_path is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Recording path not configured",
            )

        base_path = Path(settings.app_recording_path)

        # Normalize the base path to absolute path
        base_path = base_path.resolve()

        # Build the file path - handle both relative paths and filenames
        # Security: Use resolve() to prevent path traversal attacks
        resolved_file_path = (base_path / file_path).resolve()

        # Log the expected file path for debugging
        logger.warning(
            f"Recording request - Base path: {base_path}, "
            f"Requested file: {file_path}, "
            f"Expected file path: {resolved_file_path}"
        )

        # Ensure the file is within the base path (prevent path traversal)
        try:
            resolved_file_path.relative_to(base_path)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Invalid file path",
            )

        # Check if file exists
        if not resolved_file_path.exists():
            logger.warning(f"Recording file not found: {resolved_file_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording file not found",
            )

        # Check if it's a file (not a directory)
        if not resolved_file_path.is_file():
            logger.warning(f"Path is not a file: {resolved_file_path}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path is not a file",
            )

        # Determine media type based on file extension
        media_type_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
            ".m4a": "audio/mp4",
            ".flac": "audio/flac",
        }

        file_ext = resolved_file_path.suffix.lower()
        media_type = media_type_map.get(file_ext, "audio/mpeg")

        # Get file metadata for HTTP/2 support
        file_stat = resolved_file_path.stat()
        file_size = file_stat.st_size
        mtime = file_stat.st_mtime
        
        # Generate ETag for cache validation
        etag = generate_etag(resolved_file_path, file_size, mtime)
        
        # Check If-None-Match header for cache validation
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match:
            # ETag comparison: remove quotes and compare
            if_none_match_clean = if_none_match.strip('"')
            if if_none_match_clean == etag:
                return Response(status_code=status.HTTP_304_NOT_MODIFIED)
        
        # Check If-Modified-Since header
        if_modified_since = request.headers.get("If-Modified-Since")
        if if_modified_since:
            try:
                from datetime import timezone
                from email.utils import parsedate_to_datetime
                
                modified_since = parsedate_to_datetime(if_modified_since)
                from datetime import datetime
                file_mtime = datetime.fromtimestamp(mtime, tz=timezone.utc)
                if file_mtime <= modified_since:
                    return Response(status_code=status.HTTP_304_NOT_MODIFIED)
            except (ValueError, TypeError):
                pass
        
        # Parse Range header for partial content support
        range_header = request.headers.get("Range")
        range_tuple = parse_range_header(range_header, file_size)
        
        # Prepare headers for HTTP/2 support
        from datetime import datetime, timezone
        from email.utils import formatdate
        
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": media_type,
            "Content-Disposition": f'inline; filename="{resolved_file_path.name}"',
            "ETag": f'"{etag}"',
            "Cache-Control": "public, max-age=3600",
            "Last-Modified": formatdate(mtime, usegmt=True),
        }
        
        # Handle range request (206 Partial Content)
        if range_tuple:
            start, end = range_tuple
            content_length = end - start + 1
            
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            headers["Content-Length"] = str(content_length)
            
            # Return partial content
            async def generate():
                with open(resolved_file_path, "rb") as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk_size = min(8192, remaining)  # 8KB chunks
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                        remaining -= len(chunk)
            
            return StreamingResponse(
                generate(),
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                headers=headers,
                media_type=media_type,
            )
        
        # Full file request - use FileResponse with headers
        headers["Content-Length"] = str(file_size)
        
        response = FileResponse(
            path=str(resolved_file_path),
            media_type=media_type,
            filename=resolved_file_path.name,
            headers=headers,
        )
        
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving recording file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving recording file: {str(e)}",
        )
