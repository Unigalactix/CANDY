# """
# Azure Document Intelligence operations module
# """
# from azure.ai.documentintelligence import DocumentIntelligenceClient
# from azure.core.credentials import AzureKeyCredential
# from typing import Dict, Any
# import logging

# logger = logging.getLogger(__name__)


# class DocumentIntelligenceService:
#     """Service for extracting content using Azure Document Intelligence"""
    
#     def __init__(self, endpoint: str, key: str):
#         """
#         Initialize Document Intelligence Service
        
#         Args:
#             endpoint: Azure Document Intelligence endpoint
#             key: Azure Document Intelligence API key
#         """
#         self.client = DocumentIntelligenceClient(
#             endpoint=endpoint,
#             credential=AzureKeyCredential(key)
#         )
    
#     def analyze_document(self, document_bytes: bytes, model_id: str = "prebuilt-read") -> Dict[str, Any]:
#         """
#         Analyze a document and extract content
        
#         Args:
#             document_bytes: Document content as bytes
#             model_id: Model ID to use for analysis (default: "prebuilt-read")
            
#         Returns:
#             Dictionary containing extracted content and metadata
#         """
#         try:
#             logger.info(f"Analyzing document with model: {model_id}")
            
#             # Analyze the document
#             poller = self.client.begin_analyze_document(
#                 model_id=model_id,
#                 body=document_bytes,
#                 content_type="application/octet-stream"
#             )
            
#             result = poller.result()
            
#             # Extract text content
#             extracted_text = ""
#             if result.content:
#                 extracted_text = result.content
            
#             # Extract structured data
#             extracted_data = {
#                 "text": extracted_text,
#                 "pages": len(result.pages) if result.pages else 0,
#                 "tables": len(result.tables) if result.tables else 0,
#                 "key_value_pairs": len(result.key_value_pairs) if result.key_value_pairs else 0,
#                 "raw_result": result.to_dict() if hasattr(result, 'to_dict') else {}
#             }
            
#             logger.info(f"Document analyzed successfully. Pages: {extracted_data['pages']}")
#             return extracted_data
            
#         except Exception as e:
#             logger.error(f"Error analyzing document: {str(e)}")
#             raise
    
#     def extract_text(self, document_bytes: bytes, model_id: str = "prebuilt-read") -> str:
#         """
#         Extract only text content from a document
        
#         Args:
#             document_bytes: Document content as bytes
#             model_id: Model ID to use for analysis
            
#         Returns:
#             Extracted text content
#         """
#         result = self.analyze_document(document_bytes, model_id)
#         return result.get("text", "")


"""
Azure Document Intelligence operations module
"""
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class DocumentIntelligenceService:
    """Service for extracting content using Azure Document Intelligence"""
    
    def __init__(self, endpoint: str, key: str):
        """
        Initialize Document Intelligence Service
        """
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )
    
    # CHANGE 1: Update default model_id to "prebuilt-layout"
    def analyze_document(self, document_bytes: bytes, model_id: str = "prebuilt-layout") -> Dict[str, Any]:
        """
        Analyze a document and extract content
        
        Args:
            document_bytes: Document content as bytes
            model_id: Model ID to use for analysis (default: "prebuilt-layout")
            
        Returns:
            Dictionary containing extracted content and metadata
        """
        try:
            logger.info(
                "Analyzing document with model=%s",
                model_id
            )

            
            # Analyze the document
            # CHANGE 2: Add output_content_format="markdown"
            # This is crucial. It forces Azure to return the text with table characters (| -)
            # which helps the LLM understand the grid structure.
            poller = self.client.begin_analyze_document(
                model_id=model_id,
                body=document_bytes,
                content_type="application/octet-stream",
                output_content_format="markdown" 
            )
            
            result = poller.result()
            
            # Extract text content (Now contains Markdown Table syntax)
            extracted_text = ""
            if result.content:
                extracted_text = result.content
            
            logger.debug(
                "Extracted text length=%s characters",
                len(extracted_text)
            )

            # Extract structured data
            extracted_data = {
                "text": extracted_text,
                "pages": len(result.pages) if result.pages else 0,
                "tables": len(result.tables) if result.tables else 0,
                # Note: 'key_value_pairs' is not typically returned by prebuilt-layout, 
                # but we leave it here for safety as it won't crash the code.
                "key_value_pairs": len(result.key_value_pairs) if hasattr(result, 'key_value_pairs') and result.key_value_pairs else 0,
                "raw_result": result.to_dict() if hasattr(result, 'to_dict') else {}
            }
            
            logger.info(
                "Document analyzed successfully (pages=%s, tables=%s)",
                extracted_data.get("pages"),
                extracted_data.get("tables")
            )

            return extracted_data
            
        except Exception as e:
            logger.error(
                "Error analyzing document with Azure Document Intelligence",
                exc_info=True
            )

            raise
    
    # CHANGE 3: Update default model_id here as well
    def extract_text(self, document_bytes: bytes, model_id: str = "prebuilt-layout") -> str:
        """
        Extract only text content from a document
        """
        result = self.analyze_document(document_bytes, model_id)
        return result.get("text", "")