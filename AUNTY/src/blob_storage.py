"""
Azure Blob Storage operations module
"""
from azure.storage.blob import BlobServiceClient, BlobClient
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class BlobStorageService:
    """Service for interacting with Azure Blob Storage"""
    
    def __init__(self, connection_string: str):
        """
        Initialize Blob Storage Service
        
        Args:
            connection_string: Azure Storage connection string
        """
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    
    def list_blobs(self, container_name: str, prefix: Optional[str] = None) -> List[str]:
        """
        List all blobs in a container
        
        Args:
            container_name: Name of the container
            prefix: Optional prefix to filter blobs
            
        Returns:
            List of blob names
        """
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            blobs = container_client.list_blobs(name_starts_with=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(
                "Error listing blobs (container=%s, prefix=%s)",
                container_name,
                prefix,
                exc_info=True
            )

            raise
    
    def list_folders(self, container_name: str) -> List[str]:
        """
        List all folders (prefixes) in a container
        
        Args:
            container_name: Name of the container
            
        Returns:
            List of folder names (without trailing slash)
        """
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            # List all blobs and extract unique folder names from paths
            blobs = container_client.list_blobs()
            folders = set()
            
            for blob in blobs:
                blob_name = blob.name
                # Extract folder name (first part before '/')
                if '/' in blob_name:
                    folder = blob_name.split('/')[0]
                    folders.add(folder)
            
            return sorted(list(folders))
        except Exception as e:
            logger.error(
                "Error listing folders (container=%s)",
                container_name,
                exc_info=True
            )

            raise
    
    def download_blob(self, container_name: str, blob_name: str) -> bytes:
        """
        Download a blob from storage
        
        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            
        Returns:
            Blob content as bytes
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            return blob_client.download_blob().readall()
        except Exception as e:
            logger.error(
                "Error downloading blob (container=%s, blob=%s)",
                container_name,
                blob_name,
                exc_info=True
            )

            raise
    
    def upload_blob(self, container_name: str, blob_name: str, data: bytes) -> None:
        """
        Upload a blob to storage
        
        Args:
            container_name: Name of the container
            blob_name: Name of the blob (including path)
            data: Data to upload as bytes
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            blob_client.upload_blob(data, overwrite=True)
            logger.info(
                "Successfully uploaded blob (container=%s, blob=%s)",
                container_name,
                blob_name
            )

        except Exception as e:
            logger.error(
                "Error uploading blob (container=%s, blob=%s)",
                container_name,
                blob_name,
                exc_info=True
            )

            raise
    
    def upload_text(self, container_name: str, blob_name: str, text: str) -> None:
        """
        Upload text content as a blob
        
        Args:
            container_name: Name of the container
            blob_name: Name of the blob (including path)
            text: Text content to upload
        """
        data = text.encode('utf-8')
        self.upload_blob(container_name, blob_name, data)
    
    def blob_exists(self, container_name: str, blob_name: str) -> bool:
        """
        Check if a blob exists
        
        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            
        Returns:
            True if blob exists, False otherwise
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            return blob_client.exists()
        except Exception as e:
            logger.error(
                "Error checking blob existence (container=%s, blob=%s)",
                container_name,
                blob_name,
                exc_info=True
            )

            return False

