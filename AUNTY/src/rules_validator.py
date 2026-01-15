"""
Rules validation module
"""
import logging
import io
from typing import List, Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)


class RulesValidator:
    """Service for loading and managing validation rules from blob storage"""
    
    def __init__(self, blob_service, container_name: str, blob_name: str):
        self.blob_service = blob_service
        self.container_name = container_name
        self.blob_name = blob_name
        self.rules = []
        self.load_rules()
    
    def load_rules(self) -> None:
        """Load rules from Excel file in blob storage"""
        try:
            logger.info(
                "Downloading rules file from blob storage: %s/%s",
                self.container_name,
                self.blob_name
            )

            excel_bytes = self.blob_service.download_blob(self.container_name, self.blob_name)
            
            excel_file = io.BytesIO(excel_bytes)
            df = pd.read_excel(excel_file, engine='openpyxl', sheet_name=0)
            
            if df.empty:
                logger.warning("Excel file is empty")
                self.rules = []
                return
            
            # Map columns - Excel has: Check Group, Example Rule (Business), Example Logic (Pseudo / SQL-ish)
            check_group_col = None
            desc_col = None
            criteria_col = None
            
            for col in df.columns:
                col_str = str(col).strip()
                col_lower = col_str.lower()
                
                if not check_group_col and ('check group' in col_lower or col_str == 'Check Group'):
                    check_group_col = col
                elif not desc_col and ('example rule' in col_lower and 'business' in col_lower):
                    desc_col = col
                elif not criteria_col and ('example logic' in col_lower or ('logic' in col_lower and 'pseudo' in col_lower)):
                    criteria_col = col
            
            # Fallback to positional if not found
            if not check_group_col and len(df.columns) > 0:
                check_group_col = df.columns[0]
            if not desc_col and len(df.columns) > 1:
                desc_col = df.columns[1]
            if not criteria_col and len(df.columns) > 2:
                criteria_col = df.columns[2]
            
            logger.info(
                "Loaded Excel with %d rows. Columns: check_group=%s, description=%s, criteria=%s",
                len(df),
                check_group_col,
                desc_col,
                criteria_col
            )

            
            # Convert to rules
            rules = []
            for idx, row in df.iterrows():
                rule = {}
                
                if check_group_col:
                    val = row[check_group_col]
                    if pd.notna(val):
                        rule['check_group'] = str(val).strip()
                
                if desc_col:
                    val = row[desc_col]
                    if pd.notna(val):
                        rule['description'] = str(val).strip()
                
                if criteria_col:
                    val = row[criteria_col]
                    if pd.notna(val):
                        rule['validation_criteria'] = str(val).strip()
                
                # Generate rule_id if missing
                if not rule.get('rule_id'):
                    prefix = rule.get('check_group', 'RULE')
                    clean_prefix = ''.join(c for c in prefix.upper() if c.isalnum() or c == '_')[:10]
                    rule['rule_id'] = f"{clean_prefix}_{idx + 1:03d}"
                
                # Only add if it has validation criteria
                if rule.get('validation_criteria') and rule['validation_criteria'].strip():
                    rules.append(rule)
            
            self.rules = rules
            logger.info(
                "Loaded %d rules from %s/%s",
                len(self.rules),
                self.container_name,
                self.blob_name
            )

                
        except Exception:
            logger.error("Error loading rules", exc_info=True)
            self.rules = []
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """Get rules (cached - only reloads if rules list is empty)"""
        # Only reload if rules are empty (initial load or if previous load failed)
        if not self.rules:
            logger.info("Rules list is empty, reloading from blob storage...")
            self.load_rules()
        else:
            logger.debug(
                "Using cached rules (%d rules)",
                len(self.rules)
            )

        return self.rules
    
    # Removed unused methods: reload_rules() and add_rule() - not used in the application
