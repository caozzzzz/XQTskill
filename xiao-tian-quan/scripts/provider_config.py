import os


PROFILES = {
    "openai": {
        "endpoint": "https://api.openai.com/v1/embeddings",
        "model": "text-embedding-3-small",
        "api_key_env": "OPENAI_API_KEY",
        "api_key": "",
    },
    "kimi": {
        "endpoint": "",
        "model": "",
        "api_key_env": "KIMI_API_KEY",
        "api_key": "",
    },
    "deepseek": {
        "endpoint": "",
        "model": "",
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_key": "",
    },
    "local": {
        "endpoint": "http://127.0.0.1:8000/v1/embeddings",
        "model": "local-embedding-model",
        "api_key_env": "LOCAL_MODEL_API_KEY",
        "api_key": "",
    },
}


def load_profile(name):
    if name not in PROFILES:
        raise ValueError(f"Unknown provider profile: {name}")
    profile = dict(PROFILES[name])
    if not profile.get("endpoint"):
        raise ValueError(
            f"Profile '{name}' has no embedding endpoint. Configure it in provider_config.py."
        )
    if not profile.get("model"):
        raise ValueError(
            f"Profile '{name}' has no embedding model. Configure it in provider_config.py."
        )
    profile["api_key"] = profile.get("api_key") or os.environ.get(
        profile.get("api_key_env", ""), ""
    )
    return profile
