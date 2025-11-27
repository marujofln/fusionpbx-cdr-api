#!/usr/bin/env python3
"""Startup script for FusionPBX CDR API."""

import logging
import os
import uvicorn
from uvicorn.config import LOGGING_CONFIG

from app.core.config import settings

if __name__ == "__main__":
    # Get log level and ensure it's lowercase for uvicorn
    log_level = settings.app_log_level.lower()
    log_level_upper = settings.app_log_level.upper()
    numeric_level = getattr(logging, log_level_upper, logging.INFO)
    
    print(f"Starting server with log level: {log_level} (from APP_LOG_LEVEL={settings.app_log_level})")
    
    # Set environment variable for uvicorn (reloader process will respect this)
    os.environ["UVICORN_LOG_LEVEL"] = log_level
    
    # Configure root logger first - this affects all loggers
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,  # Force reconfiguration
    )
    
    # Set log levels for uvicorn loggers explicitly BEFORE uvicorn starts
    logging.getLogger("uvicorn").setLevel(numeric_level)
    logging.getLogger("uvicorn.error").setLevel(numeric_level)
    logging.getLogger("uvicorn.access").setLevel(numeric_level)
    logging.getLogger("watchfiles").setLevel(numeric_level)
    
    # Configure uvicorn's logging config to use our log level
    logging_config = LOGGING_CONFIG.copy()
    logging_config["root"] = {"level": log_level_upper, "handlers": ["default"]}
    logging_config["loggers"]["uvicorn"]["level"] = log_level_upper
    logging_config["loggers"]["uvicorn.error"]["level"] = log_level_upper
    logging_config["loggers"]["uvicorn.access"]["level"] = log_level_upper
    
    # Add watchfiles logger if it doesn't exist (used by reloader)
    if "watchfiles" not in logging_config["loggers"]:
        logging_config["loggers"]["watchfiles"] = {
            "handlers": ["default"],
            "level": log_level_upper,
            "propagate": False,
        }
    else:
        logging_config["loggers"]["watchfiles"]["level"] = log_level_upper
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=log_level,
        log_config=logging_config,
        use_colors=True,
    )
