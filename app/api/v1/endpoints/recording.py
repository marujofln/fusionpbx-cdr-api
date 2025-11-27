"""Recording endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/recording/{file_path:path}")
async def get_recording(
    file_path: str,
) -> FileResponse:
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

        # Return the file
        return FileResponse(
            path=str(resolved_file_path),
            media_type=media_type,
            filename=resolved_file_path.name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving recording file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving recording file: {str(e)}",
        )
