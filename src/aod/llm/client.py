"""LLM client wrapper with Gemini primary and OpenAI fallback"""

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
OPENAI_MODEL = "gpt-4o-mini"


@dataclass
class LLMResponse:
    """Structured response from LLM"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    provider: str = ""
    model_id: str = ""


class LLMClient(ABC):
    """Base LLM client interface"""
    
    @abstractmethod
    async def generate_json(self, prompt: str, schema: dict) -> LLMResponse:
        """Generate JSON response matching the provided schema"""
        pass
    
    @property
    @abstractmethod
    def provider(self) -> str:
        pass
    
    @property
    @abstractmethod
    def model_id(self) -> str:
        pass


class GeminiClient(LLMClient):
    """Gemini API client"""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client = None
        self._model = GEMINI_MODEL
    
    @property
    def provider(self) -> str:
        return "gemini"
    
    @property
    def model_id(self) -> str:
        return self._model
    
    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except ImportError:
                raise ImportError("google-genai package not installed")
        return self._client
    
    async def generate_json(self, prompt: str, schema: dict) -> LLMResponse:
        """Generate JSON response using Gemini"""
        try:
            from google import genai
            from google.genai import types
            
            client = self._get_client()
            
            system_prompt = (
                "You are an enterprise IT asset classification expert. "
                "Analyze the provided entity and match it to CMDB/IdP records if possible. "
                "Respond ONLY with valid JSON matching the exact schema provided. "
                "Be conservative - only return high confidence matches."
            )
            
            full_prompt = f"{prompt}\n\nRespond with JSON matching this schema:\n{json.dumps(schema, indent=2)}"
            
            response = client.models.generate_content(
                model=self._model,
                contents=[types.Content(role="user", parts=[types.Part(text=full_prompt)])],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                ),
            )
            
            if not response.text:
                return LLMResponse(success=False, error="Empty response", provider=self.provider, model_id=self.model_id)
            
            data = json.loads(response.text)
            
            if not self._validate_schema(data, schema):
                return LLMResponse(success=False, error="Response does not match schema", provider=self.provider, model_id=self.model_id)
            
            return LLMResponse(success=True, data=data, provider=self.provider, model_id=self.model_id)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Gemini returned invalid JSON: {e}")
            return LLMResponse(success=False, error=f"Invalid JSON: {e}", provider=self.provider, model_id=self.model_id)
        except Exception as e:
            logger.warning(f"Gemini API error: {e}")
            return LLMResponse(success=False, error=str(e), provider=self.provider, model_id=self.model_id)
    
    def _validate_schema(self, data: dict, schema: dict) -> bool:
        """Validate response has required keys from schema"""
        required_keys = set(schema.get("required", []))
        return required_keys.issubset(set(data.keys()))


class OpenAIClient(LLMClient):
    """OpenAI API client (fallback)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None
        self._model = OPENAI_MODEL
    
    @property
    def provider(self) -> str:
        return "openai"
    
    @property
    def model_id(self) -> str:
        return self._model
    
    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key)
            except ImportError:
                raise ImportError("openai package not installed")
        return self._client
    
    async def generate_json(self, prompt: str, schema: dict) -> LLMResponse:
        """Generate JSON response using OpenAI"""
        try:
            client = self._get_client()
            
            system_prompt = (
                "You are an enterprise IT asset classification expert. "
                "Analyze the provided entity and match it to CMDB/IdP records if possible. "
                "Respond ONLY with valid JSON matching the exact schema provided. "
                "Be conservative - only return high confidence matches."
            )
            
            full_prompt = f"{prompt}\n\nRespond with JSON matching this schema:\n{json.dumps(schema, indent=2)}"
            
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt}
                ],
                response_format={"type": "json_object"},
                timeout=30,
            )
            
            content = response.choices[0].message.content
            if not content:
                return LLMResponse(success=False, error="Empty response", provider=self.provider, model_id=self.model_id)
            
            data = json.loads(content)
            
            if not self._validate_schema(data, schema):
                return LLMResponse(success=False, error="Response does not match schema", provider=self.provider, model_id=self.model_id)
            
            return LLMResponse(success=True, data=data, provider=self.provider, model_id=self.model_id)
            
        except json.JSONDecodeError as e:
            logger.warning(f"OpenAI returned invalid JSON: {e}")
            return LLMResponse(success=False, error=f"Invalid JSON: {e}", provider=self.provider, model_id=self.model_id)
        except Exception as e:
            logger.warning(f"OpenAI API error: {e}")
            return LLMResponse(success=False, error=str(e), provider=self.provider, model_id=self.model_id)
    
    def _validate_schema(self, data: dict, schema: dict) -> bool:
        """Validate response has required keys from schema"""
        required_keys = set(schema.get("required", []))
        return required_keys.issubset(set(data.keys()))


def get_llm_client(prefer_gemini: bool = True) -> LLMClient:
    """Get LLM client, preferring Gemini if available"""
    if prefer_gemini and os.environ.get("GEMINI_API_KEY"):
        return GeminiClient()
    elif os.environ.get("OPENAI_API_KEY"):
        return OpenAIClient()
    raise RuntimeError("No LLM API key configured (GEMINI_API_KEY or OPENAI_API_KEY)")
