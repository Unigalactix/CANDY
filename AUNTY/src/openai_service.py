"""
Azure OpenAI operations module
"""
from openai import AzureOpenAI
from typing import Dict, Any, List, Optional
import json
import logging
import re
import os
from pathlib import Path
import concurrent.futures

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with Azure OpenAI"""
    
    def __init__(self, endpoint: str, api_key: str, api_version: str, deployment_name: str):

        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        self.deployment_name = deployment_name
        self.json_schema = self._load_json_schema()
    
    def _load_json_schema(self) -> str:
        """Load JSON schema from file"""
        try:
            # Get the path to the schema file relative to this module
            current_dir = Path(__file__).parent.parent
            schema_path = current_dir / "schemas" / "output_schema.json"
            
            if schema_path.exists():
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_data = json.load(f)
                    # Return formatted JSON string for inclusion in prompt
                    return json.dumps(schema_data, indent=2)
            else:
                logger.warning(f"JSON schema file not found at {schema_path}. Using default structure.")
                return ""
        except Exception as e:
            logger.error(f"Error loading JSON schema: {str(e)}")
            return ""
    
    def structure_and_validate_content(
        self,
        extracted_text: str,
        rules: List[Dict[str, Any]],
        file_name: str = ""
    ) -> Dict[str, Any]:

        try:
            logger.info(f"Structuring and validating content for file: {file_name}")
            
            # Use chunking for large documents (>50,000 characters)
            # This prevents token limit issues and ensures complete data extraction
            chunk_threshold = 50000
            doc_length = len(extracted_text)
            logger.info(f"Document length: {doc_length:,} characters, threshold: {chunk_threshold:,}")
            
            if doc_length > chunk_threshold:
                logger.info(f"Document exceeds {chunk_threshold:,} characters. Using chunking method.")
                structured_data = self._process_with_chunking(extracted_text, rules, file_name)
            else:
                # Process normally for smaller documents
                logger.info(f"Document is {doc_length:,} characters (below {chunk_threshold:,} threshold). Processing without chunking.")
                system_prompt, user_prompt = self._create_prompts(extracted_text, rules, file_name)
                response_content, is_truncated = self._call_openai(system_prompt, user_prompt)
                structured_data = self._parse_json_response(response_content, extracted_text, file_name, is_truncated=is_truncated)
            
            # Post-process: parse nested JSON strings and merge processed_text
            structured_data = self._post_process_response(structured_data, extracted_text, file_name)
            
            logger.info(f"Content structured and validated successfully for: {file_name}")
            return structured_data
            
        except Exception as e:
            logger.error(f"Error structuring content: {str(e)}")
            raise
    

    def _get_text_chunks(self, full_text: str, chunk_size: int = 15000, overlap: int = 2000) -> List[str]:

        chunks = []
        start = 0
        
        while start < len(full_text):
            end = start + chunk_size
            chunk = full_text[start:end]
            chunks.append(chunk)
            
            # Move start forward by chunk_size minus overlap
            # This ensures we include some content from previous chunk
            start += (chunk_size - overlap)
        
        logger.info(f"Split document into {len(chunks)} chunks (chunk_size={chunk_size}, overlap={overlap})")
        return chunks
    
    def _process_with_chunking(
        self,
        extracted_text: str,
        rules: List[Dict[str, Any]],
        file_name: str
    ) -> Dict[str, Any]:

        text_chunks = self._get_text_chunks(extracted_text, chunk_size=15000, overlap=2000)
        total_chunks = len(text_chunks)
        
        # This will hold the results from all threads
        chunk_results = [None] * total_chunks
        logger.info("[file=%s] Processing %d chunks in parallel", file_name, total_chunks)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_chunk = {
                executor.submit(
                    self._process_single_chunk,
                    chunk_text,
                    rules,
                    file_name,
                    i + 1,
                    total_chunks
                ): i for i, chunk_text in enumerate(text_chunks)
            }
           
            for future in concurrent.futures.as_completed(future_to_chunk):
                idx = future_to_chunk[future]
                try:
                    chunk_results[idx] = future.result()
                    logger.info(
                        "Chunk %d/%d completed successfully (stored at index %d)",
                        idx + 1,
                        total_chunks,
                        idx
                    )
 
                except Exception as e:
                    logger.error(
                        "Error processing chunk %d",
                        idx + 1,
                        exc_info=True
                    )
 
                    # Create empty result for failed chunk
                    chunk_results[idx] = {}
        
        # MERGING LOGIC
        # Initialize master JSON structure
        master_json = {
            "document_metadata": {},
            "validation_summary": {
                "total_rules_checked": 0,
                "critical_flags": 0,
                "status": "PASSED"
            },
            "rooms": [],
            "grand_total_areas": {},
            "summary_for_dwelling": {},
            "Recap of Taxes Overhead and Profit": [],
            "Recap by Room": [],
            "recap_by_category": [],
            "review_findings": []
        }
        
        total_flags = 0
        total_rules_checked = 0
        

        for i, chunk_data in enumerate(chunk_results):
            if not chunk_data:
                logger.warning(f"Chunk {i + 1} returned empty data, skipping...")
                continue
                
            # First chunk: Extract metadata
            if i == 0:
                master_json["document_metadata"] = chunk_data.get("document_metadata", {})
            
            rooms_data = chunk_data.get("rooms", [])
            if not rooms_data:
                rooms_data = chunk_data.get("areas", [])
            
            if isinstance(rooms_data, list):
                logger.debug(f"Chunk {i + 1}: Adding {len(rooms_data)} rooms to master list")
                master_json["rooms"].extend(rooms_data)
            else:
                logger.warning(f"Chunk {i + 1}: rooms_data is not a list, type: {type(rooms_data)}")
            
            # Collect validation summary data
            if "validation_summary" in chunk_data:
                vs = chunk_data["validation_summary"]
                total_rules_checked += vs.get("total_rules_checked", 0)
                total_flags += vs.get("critical_flags", 0)
            
            if chunk_data.get("grand_total_areas"):
                # Update with non-null values (defensive merging)
                for key, value in chunk_data.get("grand_total_areas", {}).items():
                    if value is not None:
                        master_json["grand_total_areas"][key] = value
            
            if chunk_data.get("summary_for_dwelling"):
                # Update with non-null values (defensive merging)
                for key, value in chunk_data.get("summary_for_dwelling", {}).items():
                    if value is not None:
                        master_json["summary_for_dwelling"][key] = value
            
            # For lists, extend them if they contain data (avoid duplicates)
            recap_taxes = chunk_data.get("Recap of Taxes Overhead and Profit", [])
            if recap_taxes:
                # Simple deduplication by description
                existing_descs = {item.get("description", "") for item in master_json["Recap of Taxes Overhead and Profit"]}
                for item in recap_taxes:
                    if item.get("description", "") not in existing_descs:
                        master_json["Recap of Taxes Overhead and Profit"].append(item)
                        existing_descs.add(item.get("description", ""))
            
            recap_by_room = chunk_data.get("Recap by Room", [])
            if recap_by_room:
                existing_room_names = {item.get("room_name", "") for item in master_json["Recap by Room"]}
                for item in recap_by_room:
                    if item.get("room_name", "") not in existing_room_names:
                        master_json["Recap by Room"].append(item)
                        existing_room_names.add(item.get("room_name", ""))
            
            recap_by_category = chunk_data.get("recap_by_category", [])
            if recap_by_category:
                existing_cats = {(item.get("category", ""), item.get("section_type", "")) for item in master_json["recap_by_category"]}
                for item in recap_by_category:
                    cat_key = (item.get("category", ""), item.get("section_type", ""))
                    if cat_key not in existing_cats:
                        master_json["recap_by_category"].append(item)
                        existing_cats.add(cat_key)
            
            review_findings = chunk_data.get("review_findings", [])
            if review_findings:
                existing_findings = {item.get("description", "") for item in master_json["review_findings"]}
                for item in review_findings:
                    if item.get("description", "") not in existing_findings:
                        master_json["review_findings"].append(item)
                        existing_findings.add(item.get("description", ""))
        
        # SMART DEDUPLICATION (Data loss fix - merges items instead of replacing)
        master_json["rooms"] = self._merge_and_deduplicate_rooms(master_json["rooms"])

        if rules and len(rules) > 0:
            actual_rules_count = len(rules)
            
            total_flags_recalculated = 0
            for room in master_json["rooms"]:
                rule_validations = room.get("rule_validations", [])
                for validation in rule_validations:
                    if validation.get("status") == "FLAGGED":
                        total_flags_recalculated += 1
            
            final_flags = total_flags_recalculated if total_flags_recalculated > 0 else total_flags
            
            master_json["validation_summary"]["total_rules_checked"] = actual_rules_count
            master_json["validation_summary"]["critical_flags"] = final_flags
            master_json["validation_summary"]["status"] = "PASSED" if final_flags == 0 else "FLAGGED"
            
            logger.info(f"Validation summary: {actual_rules_count} rules checked, {final_flags} flags found")
        else:
            # No rules provided - use sum from chunks (should be 0)
            master_json["validation_summary"]["total_rules_checked"] = total_rules_checked
            master_json["validation_summary"]["critical_flags"] = total_flags
            master_json["validation_summary"]["status"] = "PASSED" if total_flags == 0 else "FLAGGED"
        
        logger.info(f"Chunking complete. Total rooms extracted: {len(master_json['rooms'])} (after deduplication)")
        return master_json
    
    def _process_single_chunk(
        self,
        chunk_text: str,
        rules: List[Dict[str, Any]],
        file_name: str,
        chunk_number: int,
        total_chunks: int
    ) -> Dict[str, Any]:

        # Create prompts for this chunk
        system_prompt, user_prompt = self._create_prompts(
            chunk_text,
            rules,
            file_name,
            is_chunk=True,
            chunk_number=chunk_number,
            total_chunks=total_chunks
        )
        
        # Call OpenAI for this chunk
        response_content, is_truncated = self._call_openai(system_prompt, user_prompt)
        
        # Parse JSON response
        chunk_data = self._parse_json_response(response_content, chunk_text, file_name, is_truncated=is_truncated)
        
        return chunk_data
    
    def _merge_and_deduplicate_rooms(self, rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        unique_rooms = {}
        duplicate_count = 0
        
        for room in rooms:
            # 1. Normalize name and grouping for robust key generation
            room_name = str(room.get("name", "Unknown")).strip().lower()
            grouping = str(room.get("grouping", "")).strip().lower() if room.get("grouping") else ""
            
            if not room_name or room_name == "unknown":
                room_name = f"unnamed_room_{len(unique_rooms)}"
            
            room_key = f"{room_name}::{grouping}" if grouping else room_name
            
            if room_key not in unique_rooms:
                # First occurrence: ensure standard structure exists
                unique_rooms[room_key] = room.copy()
                if "line_items" not in unique_rooms[room_key]:
                    unique_rooms[room_key]["line_items"] = []
                if "sub_areas" not in unique_rooms[room_key]:
                    unique_rooms[room_key]["sub_areas"] = []
                if "rule_validations" not in unique_rooms[room_key]:
                    unique_rooms[room_key]["rule_validations"] = []
            else:
                duplicate_count += 1
                existing_room = unique_rooms[room_key]
                existing_room_name = existing_room.get("name", "Unknown")
                logger.debug(f"Merging duplicate room: '{room.get('name', 'Unknown')}' (grouping: '{grouping}') with existing '{existing_room_name}'")
                
                # 2. Safety Fix for 'NoneType' Dimensions Error
                new_dims = room.get("dimensions")
                existing_dims = existing_room.get("dimensions")
                
                if new_dims and not existing_dims:
                    existing_room["dimensions"] = new_dims
                elif isinstance(new_dims, dict) and isinstance(existing_dims, dict):
                    # Only call .items() if we are CERTAIN both are dictionaries
                    for key, value in new_dims.items():
                        if value is not None and existing_dims.get(key) is None:
                            existing_dims[key] = value

                # 3. Robust Merge for Line Items (Handles 'items' or 'line_items' keys)
                new_items = room.get("line_items") or room.get("items") or []
                existing_items = existing_room.get("line_items", [])
                
                existing_item_sigs = {
                    (str(item.get("description", "")).strip().lower(), str(item.get("quantity", "")))
                    for item in existing_items
                }
                
                for item in new_items:
                    item_sig = (str(item.get("description", "")).strip().lower(), str(item.get("quantity", "")))
                    if item_sig not in existing_item_sigs:
                        existing_items.append(item)
                        existing_item_sigs.add(item_sig)
                
                existing_room["line_items"] = existing_items

                # 4. Deep Merge for Sub-Areas
                # This ensures that if a Closet is found in two different chunks, its data merges
                new_sub_areas = room.get("sub_areas", [])
                existing_sub_areas = existing_room.get("sub_areas", [])
                
                existing_sub_names = {str(sa.get("name", "")).strip().lower() for sa in existing_sub_areas}
                
                for sub_area in new_sub_areas:
                    sa_name = str(sub_area.get("name", "")).strip().lower()
                    if sa_name and sa_name not in existing_sub_names:
                        existing_sub_areas.append(sub_area)
                        existing_sub_names.add(sa_name)
                    elif sa_name in existing_sub_names:
                        # Recursive logic: find the existing sub_area and merge its items/dims
                        for target in existing_sub_areas:
                            if str(target.get("name", "")).strip().lower() == sa_name:
                                # Merge items within the sub_area
                                t_items = target.setdefault("line_items", [])
                                s_items = sub_area.get("line_items", []) or sub_area.get("items", [])
                                t_items.extend([i for i in s_items if i not in t_items])
                                break
                
                existing_room["sub_areas"] = existing_sub_areas
                
                # 5. Merge architectural_features at room level (with fragmented feature handling)
                new_arch_features = room.get("architectural_features", [])
                existing_arch_features = existing_room.get("architectural_features", [])
                
                if new_arch_features:
                    for feature in new_arch_features:
                        f_type = str(feature.get("feature_type", "")).strip().lower()
                        f_dims = str(feature.get("dimensions_raw", "")).strip().lower()
                        f_action = str(feature.get("action_description", "")).strip()
                        
                        # Handle fragmented features: "Opens into..." as feature_type means it's actually an action_description
                        if "opens into" in f_type:
                            merged = False
                            for existing in reversed(existing_arch_features):
                                existing_dims = str(existing.get("dimensions_raw", "")).strip().lower()
                                # If existing feature has type but missing dimensions or action, merge this data
                                if existing_dims == "" or existing_dims == "none" or existing.get("action_description") is None:
                                    if f_dims and f_dims != "none":
                                        existing["dimensions_raw"] = feature.get("dimensions_raw")
                                    if f_action or f_type:
                                        existing["action_description"] = f_action if f_action else f_type
                                    merged = True
                                    break
                            
                            # If no match found, skip this invalid feature (it's likely a duplicate action_description)
                            if not merged:
                                logger.debug(f"Skipping invalid architectural feature with type '{feature.get('feature_type')}' - appears to be action_description")
                            continue
                        
                        # Standard deduplication: Use feature_type + dimensions_raw as unique identifier
                        existing_feature_sigs = {
                            (str(f.get("feature_type", "")).strip().lower(), str(f.get("dimensions_raw", "")).strip().lower())
                            for f in existing_arch_features
                        }
                        
                        feature_sig = (f_type, f_dims)
                        if feature_sig not in existing_feature_sigs:
                            # Also check if we have a feature with same type but missing dimensions (fragmented across chunks)
                            found_fragment = False
                            for existing in existing_arch_features:
                                existing_type = str(existing.get("feature_type", "")).strip().lower()
                                existing_dims = str(existing.get("dimensions_raw", "")).strip().lower()
                                if existing_type == f_type and (existing_dims == "" or existing_dims == "none") and f_dims:
                                    # Merge: existing has type but no dims, new has dims
                                    existing["dimensions_raw"] = feature.get("dimensions_raw")
                                    if f_action:
                                        existing["action_description"] = feature.get("action_description")
                                    found_fragment = True
                                    break
                                elif existing_type == f_type and existing_dims and (f_dims == "" or f_dims == "none") and f_action:
                                    # Merge: existing has type and dims, new has action_description
                                    existing["action_description"] = feature.get("action_description")
                                    found_fragment = True
                                    break
                            
                            if not found_fragment:
                                existing_arch_features.append(feature)
                    
                    existing_room["architectural_features"] = existing_arch_features
                
                # 6. Merge architectural_features within sub_areas
                for sub_area in new_sub_areas:
                    sa_name = str(sub_area.get("name", "")).strip().lower()
                    if sa_name:
                        for target_sub_area in existing_sub_areas:
                            if str(target_sub_area.get("name", "")).strip().lower() == sa_name:
                                # Merge architectural_features in this sub_area (with fragmented feature handling)
                                target_arch = target_sub_area.get("architectural_features", [])
                                new_sub_arch = sub_area.get("architectural_features", [])
                                
                                if new_sub_arch:
                                    for feature in new_sub_arch:
                                        f_type = str(feature.get("feature_type", "")).strip().lower()
                                        f_dims = str(feature.get("dimensions_raw", "")).strip().lower()
                                        f_action = str(feature.get("action_description", "")).strip()
                                        
                                        # Handle fragmented features: "Opens into..." as feature_type means it's actually an action_description
                                        if "opens into" in f_type:
                                            # This is a mis-extracted feature - it's actually an action_description
                                            merged = False
                                            for existing in reversed(target_arch):
                                                existing_dims = str(existing.get("dimensions_raw", "")).strip().lower()
                                                if existing_dims == "" or existing_dims == "none" or existing.get("action_description") is None:
                                                    if f_dims and f_dims != "none":
                                                        existing["dimensions_raw"] = feature.get("dimensions_raw")
                                                    if f_action or f_type:
                                                        existing["action_description"] = f_action if f_action else f_type
                                                    merged = True
                                                    break
                                            
                                            if not merged:
                                                logger.debug(f"Skipping invalid sub-area architectural feature with type '{feature.get('feature_type')}' - appears to be action_description")
                                            continue
                                        
                                        # Standard deduplication with fragment handling
                                        existing_sub_feature_sigs = {
                                            (str(f.get("feature_type", "")).strip().lower(), str(f.get("dimensions_raw", "")).strip().lower())
                                            for f in target_arch
                                        }
                                        
                                        feature_sig = (f_type, f_dims)
                                        if feature_sig not in existing_sub_feature_sigs:
                                            # Check for fragmented features across chunks
                                            found_fragment = False
                                            for existing in target_arch:
                                                existing_type = str(existing.get("feature_type", "")).strip().lower()
                                                existing_dims = str(existing.get("dimensions_raw", "")).strip().lower()
                                                if existing_type == f_type and (existing_dims == "" or existing_dims == "none") and f_dims:
                                                    existing["dimensions_raw"] = feature.get("dimensions_raw")
                                                    if f_action:
                                                        existing["action_description"] = feature.get("action_description")
                                                    found_fragment = True
                                                    break
                                                elif existing_type == f_type and existing_dims and (f_dims == "" or f_dims == "none") and f_action:
                                                    existing["action_description"] = feature.get("action_description")
                                                    found_fragment = True
                                                    break
                                            
                                            if not found_fragment:
                                                target_arch.append(feature)
                                    
                                    target_sub_area["architectural_features"] = target_arch
                                break
                
                # 7. Merge rule_validations (critical for split rooms across chunks)
                new_validations = room.get("rule_validations", [])
                existing_validations = existing_room.setdefault("rule_validations", [])
                
                # Deduplicate by rule name/id to avoid duplicates when same room appears in multiple chunks
                existing_rule_ids = {str(v.get("rule", "")).strip() for v in existing_validations}
                
                for val in new_validations:
                    rule_id = str(val.get("rule", "")).strip()
                    if rule_id and rule_id not in existing_rule_ids:
                        existing_validations.append(val)
                        existing_rule_ids.add(rule_id)
                    elif rule_id in existing_rule_ids:
                        # If same rule appears in both chunks, keep the one with FLAGGED status (more important)
                        for existing_val in existing_validations:
                            if str(existing_val.get("rule", "")).strip() == rule_id:
                                if val.get("status") == "FLAGGED" and existing_val.get("status") == "PASSED":
                                    # Replace PASSED with FLAGGED
                                    existing_val["status"] = "FLAGGED"
                                    existing_val["details"] = val.get("details", existing_val.get("details", ""))
                                    existing_val["severity"] = val.get("severity", existing_val.get("severity"))
                                break
        result = list(unique_rooms.values())
        if duplicate_count > 0:
            logger.info(f"Deduplication: {len(rooms)} rooms -> {len(result)} unique rooms (merged {duplicate_count} duplicates)")
        else:
            logger.info(f"Deduplication: {len(rooms)} rooms -> {len(result)} unique rooms (no duplicates found)")
        return result

    def _create_prompts(
            self, 
            extracted_text: str, 
            rules: List[Dict[str, Any]], 
        file_name: str,
        is_chunk: bool = False,
        chunk_number: int = 1,
        total_chunks: int = 1
        ) -> tuple:
        
        # --- 1. Build Schema Section ---
        schema_section = ""
        if self.json_schema:
            schema_section = f"""
    ### TARGET JSON STRUCTURE
    You must output a single JSON object.
    
    **PRODUCTION RULES:**
    1. **Use Exact Schema Keys:** You MUST use the exact keys defined in the schema (e.g., 'dimensions', 'line_items', 'sub_areas', 'architectural_features').
    2. **Exclude Nulls:** OMIT any field that is `null`, `0`, or `0.00` to save space.
    3. **No Markdown:** Output raw JSON only. Do not wrap in ```json ... ``` blocks.

    {self.json_schema}
    """

        # --- 2. Build System Prompt ---
        chunk_note = ""
        if is_chunk:
            chunk_note = f"""
    ### CHUNKING MODE
    You are processing **Chunk {chunk_number} of {total_chunks}** from a large document.
    - Focus ONLY on the content provided in this chunk.
    - Extract all rooms and line items you find in this text segment.
    - {"Extract metadata from this chunk (first chunk only)." if chunk_number == 1 else ""}
    - {"Extract totals and summaries from this chunk if present (not just last chunk)." if chunk_number == total_chunks else "Extract totals and summaries if present in this chunk."}
    """
        
        system_prompt = f"""You are a Forensic Xactimate Auditor. Your goal is a **LOSSLESS** conversion of the estimate into JSON.
    {chunk_note}
    {schema_section}

    ### 1. HIERARCHY & RECURSION PROTOCOLS (The "Tree" Structure)
    
    * **STRUCTURAL BUFFERING:** Xactimate documents often list several area headers (Main Room + Sub-rooms) before listing any items. 
    
    * **NESTING RULE:** If you see headers for sub-areas (e.g., "Closet", "Bath", "Subroom", "Alcove", "Stairs"), you MUST extract their `name`, `dimensions`, AND their specific `line_items` into the `sub_areas` array of the current Parent Room BEFORE you extract any parent room `line_items`.
    
    * **ANTI-FLATTENING:** Never place sub-room items in the parent room's `line_items` array. Keep them nested inside the sub-area's `line_items` array. Items belonging to a sub-room (e.g., a Closet) MUST be placed INSIDE that sub-room's `line_items` array, not the parent room's array.
    
    * **MAPPING:** Do not create a separate top-level room for a sub-area if it is visually nested under a parent; keep it in the `sub_areas` array.
    
    * **TYPE A: GROUPING (Parent)**
        * **Detection:** Headers like "Main Level", "Dwelling", "Exterior" that have NO dimensions and NO line items directly under them.
        * **Action:** Set `grouping` field. Rooms following this header should have this grouping value.
    
    * **TYPE B: STANDARD ROOM**
        * **Detection:** Headers like "Kitchen", "Living Room" followed by dimensions (SF/LF).
        * **Action:** Create a room entry. Extract `dimensions`. Then scan ahead for sub-rooms and populate the `sub_areas` array with each sub-area's `name`, `dimensions`, AND `line_items` BEFORE extracting the parent room's `line_items`.
    
    * **TYPE C: SUB-ROOM (Child)**
        * **Detection:** Small headers (e.g., "Subroom: Closet", "Alcove", "Stairs", "Toilet Room") listed *inside* or *immediately after* a Main Room.
        * **Action:** Extract the sub-area's `name`, `dimensions`, AND its specific `line_items` into the parent room's `sub_areas` array. **CRITICAL:** Do NOT create a separate top-level room entry. Items belonging to this sub-room MUST be placed in the sub-area's `line_items` array, NOT in the parent room's `line_items`. Do NOT extract parent room line items until all sub-areas (with their line_items) are identified and added to `sub_areas`.

    * **TYPE D: ORPHAN ITEMS (Edge Case)**
        * **Detection:** Line items found under headers like "Estimate: 007968", "Total: 007121", "Estimate ID: 007121", or at the start/end of the file (e.g., Permits, Debris Removal) that have NO room name associated with them.
        * **Action:** Create a room entry named "General Items" to hold these items. **DO NOT SKIP THESE.** These are often high-value items that must be captured.

    ### 2. DATA EXTRACTION PROTOCOLS
    * **Metadata:** Deep scan the first 3 pages. Distinguish "Insured Mailing Address" vs "Property Address".
    * **Line Items:** Extract **EVERY** single item.
        * ** DYNAMIC SUBCATEGORY GROUPING: Scan for standalone, bold, or uppercase section headers (e.g., "FLOOR", "MITIGATION") and assign the exact text string to the subcategory_group field for all line items appearing directly beneath it until a new header is found.
        * ** NULL ASSIGNMENT: If a line item is found without a preceding section header in the current area, or if the document layout is a flat list, you MUST set subcategory_group to null.
        * **Depreciation:** Capture exactly as strings (e.g., "<50.00>", "(50.00)").
        * **Pagination Check:** You must process the document sequentially page-by-page. Do not stop until you reach the end of the text.
        * **ANTI-FLATTENING:** Do not list a Room's line items and then a Sub-room's details afterward. Group all structural definitions (Room -> Sub-rooms) together before the items.
    
    ### 3. ARCHITECTURAL FEATURE PROTOCOL
    
    **CRITICAL:** Xactimate PDFs represent architectural features as fragmented data. Labels (e.g., "Door", "Window", "Missing Wall") appear as standalone headers, with dimensions and action descriptions on subsequent lines.
    
    * **Header Matching:** If you see standalone labels like "Door", "Window", or "Missing Wall", these define the `feature_type`.
    
    * **Contextual Binding:** Any dimensions (e.g., "3' 6 1/2\" X 8'") and action descriptions (e.g., "Opens into Exterior") that follow a type label MUST be merged into that specific feature.
    
    * **Invalid Feature Names:** A `feature_type` should NEVER be "Opens into..." or start with "Opens into". If you find text starting with "Opens into", it is an `action_description` for the preceding feature, NOT a new feature type.
    
    * **Buffer Logic:** When you see a feature type label (e.g., "Door"), buffer it until you find the matching dimension line. Do not create a feature entry until you have both the type and dimensions.
    
    * **Feature Structure:** Each architectural feature must have:
        - `feature_type`: Standard type (Door, Window, Missing Wall, etc.) - NEVER "Opens into..."
        - `dimensions_raw`: Raw dimension string (e.g., "3' 6 1/2\" X 8'")
        - `action_description`: Action text (e.g., "Opens into Exterior", "Opens into KITCHEN_AREA")

    ### 4. CRITICAL INTEGRITY RULES for PRODUCTION
    
    1. VALIDATION STATUS INTEGRITY: If your internal calculation for a rule results in a "FLAGGED" conclusion in the details text, you MUST set the 'status' key to "FLAGGED". Never output "PASSED" if the logic indicates a failure.
    
    2. FEATURE TYPE NAMING: "Opens into..." is NEVER a feature_type. It is always an 'action_description'. If you see "Opens into", look at the preceding label (e.g., Door, Missing Wall) to determine the 'feature_type'.
    
    3. MANDATORY AUDIT: Every room object MUST contain a 'rule_validations' array. Do not skip auditing any area.

    ### 5. VALIDATION PROTOCOLS (MANDATORY - Real-Time Check)
    **CRITICAL:** You must run validations **FOR EVERY ROOM** immediately after extracting its line items. **VALIDATION IS NOT OPTIONAL.**
    
    * **Mandatory Requirement:** Every room in your output MUST have a `rule_validations` array. If a room has no validations, it means you failed to check it.
    
    * **Complete Rule Coverage (CRITICAL):** You MUST evaluate each room against **ALL applicable rules** from the rules list provided in STEP 1. Do NOT skip rules. Check:
        - **ALL Quantity matching rules** (e.g., QUANTITYME_001: Paint SF vs Wall Area, QUANTITYME_003: Flooring SF vs Floor Area)
        - **ALL Scope completeness rules** (e.g., SCOPECOMPL_007: Drywall replacement requires texture, Paint job requires primer/sealer)
        - **ALL Pricing & Labor rules** (e.g., PRICINGLAB_012: Unit cost exceeds price-list threshold, Labor hours outside expected range)
        - **ALL Material/Labor Pairing rules** (e.g., MATERIALLA_014: Paint requires prep/masking, Cabinet install requires hardware)
        - **ALL Room Consistency rules** (e.g., Walls painted but ceiling never addressed)
        - **ALL other applicable rules** from the complete ruleset
    
    * **Rule ID Consistency:** Use the exact `rule_id` from the validation rules provided (e.g., QUANTITYME_001, QUANTITYME_003, PRICINGLAB_012, MATERIALLA_014, SCOPECOMPL_007). This allows post-processing to track which rules were checked.
    
    * **INTEGRITY RULE (CRITICAL - NO EXCEPTIONS):** Your `status` field MUST match your calculation logic. If your math shows a rule has failed (e.g., "Paint SF (264.94) > Wall Area (205.35), FLAGGED"), you MUST set `status: "FLAGGED"`. **DO NOT default to "PASSED" when your own calculations show a failure.** If your details say "FLAGGED" or show a violation, the status MUST be "FLAGGED".
    
    * **Math Logic:** If `Rule: Paint > Walls`, calculate `Paint_Qty` vs `(Parent_Walls + Sum(Sub_Area_Walls))`. If Paint_Qty > Walls, status MUST be "FLAGGED".
    * **Scope Logic:** Scan the current Room AND its Sub-areas for required items. If required items are missing, status MUST be "FLAGGED".
    * **Evidence:** Populate `rule_validations[].details` with specific evidence (quantities, calculations, missing items, etc.). The details must clearly state whether the rule passed or failed.
    * **Status Alignment:** The `status` field must accurately reflect what is stated in `details`. If details say "does not exceed" and shows correct math, use "PASSED". If details say "exceeds" or shows violation, use "FLAGGED".
    * **Severity:** Include severity level if provided in the rule.

    ### 6. UNMAPPED DATA
    * Capture non-standard text in `unmapped`.
    """
        
        # --- 3. Build User Prompt ---
        rules_text = self._format_rules_for_prompt(rules)
        
        # Add chunk context if processing a chunk
        chunk_context = ""
        if is_chunk:
            if chunk_number == 1:
                chunk_context = f"""
    ### CHUNK CONTEXT (IMPORTANT)
    This is **Chunk {chunk_number} of {total_chunks}** from a large document.
    - **YOUR TASK:** Extract metadata and all rooms/areas found in this chunk.
    - Extract totals and summaries if present in this chunk (they may span multiple chunks).
    - **OVERLAP HANDLING:** If you see a room header at the start that seems incomplete, 
      it may be continued from the previous chunk. Extract it normally.
    """
            elif chunk_number == total_chunks:
                chunk_context = f"""
    ### CHUNK CONTEXT (IMPORTANT)
    This is **Chunk {chunk_number} of {total_chunks}** (FINAL CHUNK).
    - **YOUR TASK:** Extract all rooms/areas AND the totals/summaries from this chunk.
    - **CRITICAL:** Extract `grand_total_areas`, `summary_for_dwelling`, and all recap tables.
    - **OVERLAP HANDLING:** The start of this chunk may overlap with previous chunk. 
      Extract rooms normally, but avoid duplicating rooms already extracted.
    """
            else:
                chunk_context = f"""
    ### CHUNK CONTEXT (IMPORTANT)
    This is **Chunk {chunk_number} of {total_chunks}** from a large document.
    - **YOUR TASK:** Extract ONLY the rooms/areas found in this chunk.
    - **DO NOT** extract metadata or totals (those come from first/last chunks).
    - **OVERLAP HANDLING:** The start/end of this chunk overlaps with adjacent chunks.
      Extract rooms normally - duplicates will be handled during merging.
    """
        
        # Build user_prompt (always, regardless of chunking)
        user_prompt = f"""
    ### CONTEXT
    Source File: {file_name}
    {chunk_context}
    ### STEP 1: VALIDATION RULES
    {rules_text}

    ### STEP 2: RAW ESTIMATE CONTENT
    {extracted_text}

    ### INSTRUCTION
    Process the content in this **STRICT ORDER**:
    {f'''
    1.  **METADATA (FIRST CHUNK ONLY):** Extract Company, Adjuster, Insured.
    2.  **AREA DEFINITION:** For each section, capture the Main Room AND all its Sub-areas first.
        * Identify the Room/Area name and dimensions.
        * **IMMEDIATELY scan for associated Sub-areas** (Closets, alcoves, toilet rooms, etc.).
        * **CRITICAL:** Populate the `sub_areas` array with each sub-area's `name`, `dimensions`, AND its specific `line_items` array. Items that belong to a sub-room MUST be placed in that sub-room's `line_items`, NOT in the parent room's `line_items`.
        * **STRUCTURAL BUFFERING:** Do not extract parent room `line_items` until the complete structural tree (Parent + Sub-areas with their own line_items) is defined.
    3.  **LINE ITEMS:** Only after the structural tree (Parent + Sub-areas with their line_items) is defined, extract the parent room's `line_items`. **ENSURE:** Items belonging to a sub-room (e.g., a Closet) are placed INSIDE that sub-room's `line_items` array, not the parent room's array.
    4.  **VALIDATION (MANDATORY AUDIT):** For EVERY room extracted, you MUST include the `rule_validations` array immediately after its `line_items`. You MUST evaluate the room against **ALL applicable rules** provided in STEP 1. Use the exact `rule_id` (e.g., QUANTITYME_001, QUANTITYME_003, PRICINGLAB_012, MATERIALLA_014, SCOPECOMPL_007) from the rules for each validation entry. If a rule is not applicable (e.g., a flooring rule for a room with no flooring items), you may omit it, but **ALL applicable rules must be checked**. 
    
    **INTEGRITY RULE:** If your calculation or logic shows a rule has failed (e.g., "Paint SF (264.94) > Wall Area (205.35)"), you MUST set `status: "FLAGGED"`. Do NOT default to "PASSED" when your own math shows a violation. The `status` field MUST match what is stated in the `details` field. If details say "FLAGGED" or show a violation, status MUST be "FLAGGED". **DO NOT SKIP VALIDATIONS FOR ANY ROOM.**
    5.  **TOTALS:** Deep-scan the end of the text for the "Summary for Dwelling" and "Grand Total Areas" tables if present in this chunk.
        * **Note:** These tables use dots (e.g., "Subtotal ........ 1,234.56"). You must map these values accurately to the schema keys.
    ''' if is_chunk else '''
    1.  **METADATA:** Extract Company, Adjuster, Insured.
    2.  **AREA DEFINITION:** For each section, capture the Main Room AND all its Sub-areas first.
        * Identify the Room/Area name and dimensions.
        * **IMMEDIATELY scan for associated Sub-areas** (Closets, alcoves, toilet rooms, etc.).
        * **CRITICAL:** Populate the `sub_areas` array with each sub-area's `name`, `dimensions`, AND its specific `line_items` array. Items that belong to a sub-room MUST be placed in that sub-room's `line_items`, NOT in the parent room's `line_items`.
        * **STRUCTURAL BUFFERING:** Do not extract parent room `line_items` until the complete structural tree (Parent + Sub-areas with their own line_items) is defined.
    3.  **LINE ITEMS:** Only after the structural tree (Parent + Sub-areas with their line_items) is defined, extract the parent room's `line_items`. **ENSURE:** Items belonging to a sub-room (e.g., a Closet) are placed INSIDE that sub-room's `line_items` array, not the parent room's array.
        * **ANTI-LAZINESS RULE:** You are FORBIDDEN from generating the 'Totals' section until you have extracted the line items from the **LAST PAGE** of the text.
        * If you see more pages of text, you MUST continue extracting items. Do not summarize.
    4.  **VALIDATION (MANDATORY AUDIT):** For EVERY room extracted, you MUST include the `rule_validations` array immediately after its `line_items`. You MUST evaluate the room against **ALL applicable rules** provided in STEP 1. Use the exact `rule_id` (e.g., QUANTITYME_001, QUANTITYME_003, PRICINGLAB_012, MATERIALLA_014, SCOPECOMPL_007) from the rules for each validation entry. If a rule is not applicable (e.g., a flooring rule for a room with no flooring items), you may omit it, but **ALL applicable rules must be checked**. 
    
    **INTEGRITY RULE:** If your calculation or logic shows a rule has failed (e.g., "Paint SF (264.94) > Wall Area (205.35)"), you MUST set `status: "FLAGGED"`. Do NOT default to "PASSED" when your own math shows a violation. The `status` field MUST match what is stated in the `details` field. If details say "FLAGGED" or show a violation, status MUST be "FLAGGED". **DO NOT SKIP VALIDATIONS FOR ANY ROOM.**
    5.  **TOTALS:** Deep-scan the end of the text for the "Summary for Dwelling" and "Grand Total Areas" tables. Only AFTER you have processed the final page of text.
        * **Note:** These tables use dots (e.g., "Subtotal ........ 1,234.56"). You must map these values accurately to the schema keys.
    5.  **FINISH:** Ensure JSON is closed properly.
    '''}
    
    **REMINDER:** Exclude all `null` fields to ensure the output fits.
    """
        
        return system_prompt, user_prompt
    
    def _call_openai(self, system_prompt: str, user_prompt: str) -> tuple[str, bool]:
        """Call Azure OpenAI API and return response content and truncation status"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        max_tokens = 32000
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.2,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
        except Exception as e:
            logger.warning(f"JSON response format not supported, using default: {str(e)}")
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.2,
                max_tokens=max_tokens
            )
        
        response_content = response.choices[0].message.content.strip()
    
        # Check if response was truncated (finish_reason indicates truncation)
        finish_reason = response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else None
        is_truncated = finish_reason == "length" or (len(response_content) > max_tokens * 3)  # Rough estimate: 3 chars per token
        
        if is_truncated:
            logger.warning(f"Response appears truncated (finish_reason: {finish_reason}, length: {len(response_content)}) - will attempt to fix")
        
        return response_content, is_truncated
    
    def _parse_json_response(self, response_content: str, extracted_text: str, file_name: str, is_truncated: bool = False) -> Dict[str, Any]:
        """Parse JSON response with multiple fallback strategies"""
        # Strategy 1: Direct JSON parsing
        try:
            return json.loads(response_content)
        except json.JSONDecodeError as e:
            logger.debug(f"Direct JSON parsing failed: {str(e)[:200]}")
        
        # Strategy 2: Extract from markdown code blocks
        try:
            if "```json" in response_content:
                start = response_content.find("```json") + 7
                end = response_content.find("```", start)
                if end > start:
                    return json.loads(response_content[start:end].strip())
            elif "```" in response_content:
                start = response_content.find("```") + 3
                end = response_content.find("```", start)
                if end > start:
                    return json.loads(response_content[start:end].strip())
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Markdown extraction failed: {str(e)[:200]}")
        
        # Strategy 3: Find JSON object boundaries
        try:
            start_idx = response_content.find('{')
            end_idx = response_content.rfind('}')
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_content[start_idx:end_idx+1]
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"Boundary extraction failed: {str(e)[:200]}")
            # Strategy 3b: Try to fix malformed/truncated JSON
            # Check if response looks truncated (ends with incomplete value)
            looks_truncated = (
                response_content.rstrip().endswith('.') or 
                response_content.rstrip().endswith(',') or
                not response_content.rstrip().endswith('}') or
                response_content.count('{') != response_content.count('}')
            )
            
            try:
                start_idx = response_content.find('{')
                if start_idx >= 0:
                    # Try fixing the full response first (with truncation detection)
                    fixed_json = self._try_fix_malformed_json(response_content[start_idx:], is_truncated=looks_truncated)
                    if fixed_json:
                        return json.loads(fixed_json)
                    # If that fails, try fixing just up to the last complete }
                    end_idx = response_content.rfind('}')
                    if end_idx > start_idx:
                        fixed_json = self._try_fix_malformed_json(response_content[start_idx:end_idx+1], is_truncated=looks_truncated)
                        if fixed_json:
                            return json.loads(fixed_json)
            except Exception as fix_error:
                logger.debug(f"JSON fix attempt failed: {str(fix_error)[:200]}")
                pass
        
        # Strategy 4: Clean and retry
        try:
            cleaned = response_content[response_content.find('{'):response_content.rfind('}')+1]
            if cleaned:
                return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Log detailed error information (only if all parsing strategies failed)
        error_info = f"Response length: {len(response_content)}"
        if len(response_content) > 0:
            error_info += f", First 200 chars: {response_content[:200]}"
            error_info += f", Last 200 chars: {response_content[-200:]}"
        
        logger.warning(f"Could not parse JSON response for {file_name} after all strategies. {error_info}")
        
        # Fallback: return structure with raw response
        return {
            "structured_content": {
                "processed_text": response_content
            },
            "validation": {
                "is_valid": True,
                "violations": [],
                "warnings": ["Could not parse structured JSON response - will attempt parsing in post-processing"]
            },
            "metadata": {
                "source_file": file_name
            }
        }
    
    def _try_fix_malformed_json(self, json_str: str, is_truncated: bool = False) -> Optional[str]:
        """Try to fix malformed or truncated JSON with basic fixes"""
        if not json_str or not json_str.strip().startswith('{'):
            return None
        
        fixed = json_str
        
        # Basic fix: Remove trailing commas before closing brackets/braces
        fixed = re.sub(r',\s*}', '}', fixed)
        fixed = re.sub(r',\s*]', ']', fixed)
        
        if is_truncated:
            last_complete_pos = -1
            
            # Try to find last complete number (ends with , or } or ])
            for match in re.finditer(r':\s*([+-]?\d*\.?\d+)\s*([,}\]])', fixed):
                last_complete_pos = match.end()
            
            # If we found a complete value, truncate everything after it (except closing braces)
            if last_complete_pos > 0:
                prefix = fixed[:last_complete_pos]
                if prefix.rstrip().endswith(','):
                    prefix = prefix.rstrip()[:-1] 
                fixed = prefix
    
        fixed = re.sub(r':\s*(\d+\.)\s*$', r': null', fixed, flags=re.MULTILINE)
        fixed = re.sub(r':\s*(\d+)\s*$', r': null', fixed, flags=re.MULTILINE)
        fixed = re.sub(r':\s*"([^"]*?)\s*$', r': null', fixed, flags=re.MULTILINE)
        fixed = re.sub(r':\s*([+-]?\d*\.?\d*)\s*,\s*$', r': null', fixed, flags=re.MULTILINE)
        
        if is_truncated:
            open_braces = fixed.count('{') - fixed.count('}')
            open_brackets = fixed.count('[') - fixed.count(']')
            if open_braces > 0 or open_brackets > 0:
                # Remove any trailing incomplete content before closing
                # Remove trailing commas
                fixed = fixed.rstrip().rstrip(',')
                fixed += ']' * max(0, open_brackets)
                fixed += '}' * max(0, open_braces)
        
        # Try parsing the fixed version
        try:
            json.loads(fixed)
            logger.info("Successfully fixed malformed JSON")
            return fixed
        except json.JSONDecodeError as e:
            # If still failing, try one more aggressive fix: remove the last incomplete key-value pair
            if is_truncated:
                # Find the last complete object/array closing
                last_brace = fixed.rfind('}')
                last_bracket = fixed.rfind(']')
                last_complete = max(last_brace, last_bracket)
                
                if last_complete > 0:
                    # Try to find the start of the last incomplete key-value pair
                    # Look backwards from last_complete for the last colon
                    search_start = max(0, last_complete - 500)  # Search last 500 chars
                    last_colon = fixed.rfind(':', search_start, last_complete)
                    
                    if last_colon > 0:
                        # Find the start of this key (look for quote or word boundary before colon)
                        key_start = fixed.rfind('"', search_start, last_colon)
                        if key_start > 0:
                            # Remove from key_start to end, then close properly
                            prefix = fixed[:key_start].rstrip().rstrip(',')
                            open_braces = prefix.count('{') - prefix.count('}')
                            open_brackets = prefix.count('[') - prefix.count(']')
                            prefix += ']' * max(0, open_brackets)
                            prefix += '}' * max(0, open_braces)
                            
                            try:
                                json.loads(prefix)
                                logger.info("Successfully fixed malformed JSON by removing incomplete key-value pair")
                                return prefix
                            except json.JSONDecodeError:
                                pass
            
            return None
    
    def _post_process_response(
        self, 
        structured_data: Dict[str, Any], 
        extracted_text: str, 
        file_name: str
    ) -> Dict[str, Any]:
        """Post-process response: parse nested JSON strings in the actual data"""
        # Recursively parse any JSON strings in the response (useful for nested data)
        # Skip structured_content/validation processing as they're removed in app.py
        structured_data = self._parse_nested_json_strings(structured_data)
        
        return structured_data
    
    
    def _parse_nested_json_strings(self, obj: Any) -> Any:
        """Recursively parse JSON strings in the response object"""
        if isinstance(obj, str):
            if obj.strip().startswith(('{', '[')):
                try:
                    return self._parse_nested_json_strings(json.loads(obj))
                except (json.JSONDecodeError, ValueError):
                    pass
            return obj
        elif isinstance(obj, dict):
            return {key: self._parse_nested_json_strings(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._parse_nested_json_strings(item) for item in obj]
        else:
            return obj
    
    def _format_rules_for_prompt(self, rules: List[Dict[str, Any]]) -> str:
        """Format rules for inclusion in the prompt"""
        if not rules:
            return "No specific validation rules provided."
        
        # Group rules by check_group
        grouped_rules = {}
        ungrouped_rules = []
        
        for rule in rules:
            check_group = rule.get("check_group", "")
            if check_group:
                grouped_rules.setdefault(check_group, []).append(rule)
            else:
                ungrouped_rules.append(rule)
        
        formatted_rules = []
        
        # Format grouped rules
        for check_group in sorted(grouped_rules.keys()):
            formatted_rules.append(f"\n### {check_group}")
            formatted_rules.extend(self._format_rule_list(grouped_rules[check_group]))
        
        # Format ungrouped rules
        if ungrouped_rules:
            if formatted_rules:
                formatted_rules.append("\n### Other Rules")
            formatted_rules.extend(self._format_rule_list(ungrouped_rules))
        
        return "\n".join(formatted_rules)
    
    def _format_rule_list(self, rules: List[Dict[str, Any]]) -> List[str]:
        """Format a list of rules"""
        formatted = []
        for rule in rules:
            rule_id = rule.get("rule_id", "")
            description = rule.get("description", "")
            criteria = rule.get("validation_criteria", "")
            
            rule_text = f"**{rule_id}**"
            if description:
                rule_text += f": {description}"
            if criteria:
                rule_text += f"\n  Logic: {criteria}"
            
            formatted.append(rule_text)
        return formatted
