"""
LLM-based code analysis.
"""

import json
import openai
from typing import Dict, Any, List
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """
    Use LLM for advanced code analysis.
    """

    def __init__(self):
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.model = getattr(settings, 'LLM_MODEL', 'gpt-3.5-turbo')

    def analyze_code(self, code: str, file_path: str) -> Dict[str, Any]:
        """
        Analyze code using LLM.
        """
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            return {}

        try:
            openai.api_key = self.api_key
            
            prompt = f"""
            Analyze this code for:
            1. Code quality issues
            2. Potential bugs
            3. Security vulnerabilities
            4. Performance issues
            5. Maintainability issues
            
            File: {file_path}
            Code:
            ```python
            {code[:3000]}