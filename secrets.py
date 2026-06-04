"""Centralized secrets loader.

Reads secrets from environment variables first, then from .env file,
then falls back to the legacy config files (for backward compatibility).
"""
import json
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
ENV_FILE = PROJECT_ROOT / '.env'

ENV_PATTERN = re.compile(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$')


def _load_env_file():
    """Load .env file into os.environ without overwriting existing values."""
    if not ENV_FILE.exists():
        return
    try:
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = ENV_PATTERN.match(line)
                if not m:
                    continue
                key, value = m.group(1), m.group(2).strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                os.environ.setdefault(key, value)
    except OSError:
        pass


_load_env_file()


def _expand_env_placeholders(value):
    """Replace ${VAR_NAME} placeholders with environment values."""
    if not isinstance(value, str):
        return value
    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, '')
    return re.sub(r'\$\{([A-Z_][A-Z0-9_]*)\}', replacer, value)


def get_secret(key, config_path=None, config_key=None, default=None):
    """Get a secret from env, with optional fallback to a config file."""
    env_value = os.environ.get(key)
    if env_value:
        return env_value
    if config_path and config_key:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            value = data.get(config_key, '')
            value = _expand_env_placeholders(value)
            if value and not value.startswith('${'):
                return value
        except (OSError, json.JSONDecodeError):
            pass
    return default


def get_telegram_token():
    return get_secret('TELEGRAM_BOT_TOKEN', PROJECT_ROOT / 'config' / 'telegram.json', 'bot_token')


def get_newsapi_key():
    return get_secret('NEWS_API_KEY', PROJECT_ROOT / 'config' / 'sources.json', 'newsapi_key')


def get_finnhub_key():
    return get_secret('FINNHUB_API_KEY', PROJECT_ROOT / 'config' / 'sources.json', 'finnhub_key')
