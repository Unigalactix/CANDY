"""
Configuration management for Azure services
"""
import os
from dotenv import load_dotenv

import logging

logger = logging.getLogger(__name__)


# Load environment variables
load_dotenv()


class Config:
    """Application configuration"""

    # Logging Configuration
    LOG_BLOB_CONTAINER = os.getenv("LOG_BLOB_CONTAINER", "vanguardlogs")
    
    # Azure Blob Storage Configuration
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "documents")
    AZURE_STORAGE_OUTPUT_CONTAINER = os.getenv("AZURE_STORAGE_OUTPUT_CONTAINER", "processed-documents")
    
    # Azure Document Intelligence Configuration
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    AZURE_DOCUMENT_INTELLIGENCE_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
    
    # Application Configuration
    RULES_FILE_PATH = os.getenv("RULES_FILE_PATH", "rules/rules.json")  # Legacy: not used when loading from blob
    RULES_BLOB_CONTAINER = os.getenv("RULES_BLOB_CONTAINER", "samplefiles")
    RULES_BLOB_FILE = os.getenv("RULES_BLOB_FILE", "POC_ruleset-examples.xlsx")
    
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present"""
        logger.info("Validating application configuration")
        logger.info(
            "Log container configured as: %s",
            cls.LOG_BLOB_CONTAINER
        )


        required_vars = [
            ("AZURE_STORAGE_CONNECTION_STRING", cls.AZURE_STORAGE_CONNECTION_STRING),
            ("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", cls.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT),
            ("AZURE_DOCUMENT_INTELLIGENCE_KEY", cls.AZURE_DOCUMENT_INTELLIGENCE_KEY),
            ("AZURE_OPENAI_ENDPOINT", cls.AZURE_OPENAI_ENDPOINT),
            ("AZURE_OPENAI_API_KEY", cls.AZURE_OPENAI_API_KEY),
            ("AZURE_OPENAI_DEPLOYMENT_NAME", cls.AZURE_OPENAI_DEPLOYMENT_NAME),
        ]

        missing = [var[0] for var in required_vars if not var[1]]

        if missing:
            logger.error(
                "Missing required environment variables: %s",
                ", ".join(missing)
            )
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        logger.info("Configuration validation successful")
        return True


