import json
import os
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class OpenRouterClient:
    DEFAULT_API_URL = "https://openrouter.ai/v1/chat/completions"
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, api_key=None, model=None, api_url=None):
        self.api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
        self.model = model or os.environ.get('OPENROUTER_MODEL') or self.DEFAULT_MODEL
        self.api_url = api_url or os.environ.get('OPENROUTER_API_URL') or self.DEFAULT_API_URL
        if not self.api_key:
            raise ValueError('OpenRouter API key is required. Set OPENROUTER_API_KEY.')

    def _build_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

    def _build_payload(self, question, choices):
        prompt = [
            {
                'role': 'system',
                'content': 'You are a quiz assistant. Choose the correct answer from the provided options.'
            },
            {
                'role': 'user',
                'content': self._build_prompt(question, choices)
            }
        ]
        return {
            'model': self.model,
            'messages': prompt,
            'temperature': 0.0,
            'max_tokens': 128
        }

    @staticmethod
    def _build_prompt(question, choices):
        body = [f'Question: {question}', 'Choices:']
        for index, choice in enumerate(choices, start=1):
            body.append(f'{index}. {choice}')
        body.append('Answer only with the number of the best choice. Do not add any explanation.')
        return '\n'.join(body)

    @staticmethod
    def _normalize_response_text(raw):
        if raw is None:
            return None
        text = raw.strip()
        if not text:
            return None
        # remove any surrounding quotes or punctuation
        text = re.sub(r'^"|"$', '', text).strip()
        return text

    def _parse_choice(self, response_text, num_choices):
        if not response_text:
            return None
        response_text = response_text.strip()
        # first try to match a number
        match = re.search(r'\b([1-9][0-9]{0,2})\b', response_text)
        if match:
            choice_number = int(match.group(1))
            if 1 <= choice_number <= num_choices:
                return choice_number - 1
        return None

    def _extract_text(self, response_data):
        if not isinstance(response_data, dict):
            return None
        # typical chat response fields
        if 'choices' in response_data and isinstance(response_data['choices'], list) and response_data['choices']:
            first = response_data['choices'][0]
            if isinstance(first, dict):
                if 'message' in first and isinstance(first['message'], dict):
                    return first['message'].get('content')
                if 'text' in first:
                    return first.get('text')
        if 'output' in response_data and isinstance(response_data['output'], list) and response_data['output']:
            first = response_data['output'][0]
            if isinstance(first, dict):
                if 'content' in first and isinstance(first['content'], list) and first['content']:
                    first_content = first['content'][0]
                    if isinstance(first_content, dict) and 'text' in first_content:
                        return first_content['text']
                    if isinstance(first_content, str):
                        return first_content
        return None

    def select_choice(self, question, choices):
        payload = self._build_payload(question, choices)
        data = json.dumps(payload).encode('utf-8')
        req = Request(self.api_url, data=data, headers=self._build_headers(), method='POST')
        try:
            with urlopen(req, timeout=30) as resp:
                content = resp.read().decode('utf-8')
                result = json.loads(content)
                text = self._extract_text(result)
                normalized = self._normalize_response_text(text)
                if normalized is None:
                    raise ValueError('Empty model response')
                index = self._parse_choice(normalized, len(choices))
                if index is None:
                    raise ValueError(f'Could not parse choice number from model response: {normalized}')
                # return index (0-based), the normalized text, and the raw extracted text for logging
                return index, normalized, text
        except HTTPError as e:
            body = ''
            try:
                body = e.read().decode('utf-8', errors='ignore')
            except Exception:
                pass
            raise RuntimeError(f'OpenRouter API error {e.code}: {body}')
        except URLError as e:
            raise RuntimeError(f'OpenRouter connection error: {e.reason}')
        except json.JSONDecodeError as e:
            raise RuntimeError(f'OpenRouter response parse error: {e}')
