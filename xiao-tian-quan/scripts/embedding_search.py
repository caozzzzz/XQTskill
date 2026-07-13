import hashlib
import json
import math
import os
import re
import urllib.request
from pathlib import Path

from provider_config import load_profile


class EmbeddingIndex:

    def __init__(self, provider, model, dimensions, documents, profile=""):
        self.provider = provider
        self.model = model
        self.dimensions = dimensions
        self.documents = documents
        self.profile = profile

    @classmethod
    def from_records(cls, records, provider="local-hash", model="", dimensions=384, profile=""):
        embedder = Embedder(provider, model, dimensions, profile)
        documents = []
        for index, record in enumerate(records):
            text = _document_text(record)
            documents.append({
                "record_index": index,
                "text": text,
                "vector": embedder.embed(text),
                "record": record,
            })
        return cls(provider, model, dimensions, documents, profile)

    @classmethod
    def load(cls, path):
        with Path(path).open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
        return cls(
            data.get("provider", "local-hash"),
            data.get("model", ""),
            data.get("dimensions", 384),
            data.get("documents", []),
            data.get("profile", ""),
        )

    def save(self, path):
        data = {
            "version": 1,
            "provider": self.provider,
            "model": self.model,
            "dimensions": self.dimensions,
            "profile": self.profile,
            "documents": self.documents,
        }
        with Path(path).open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def search(self, query, scenes=None, branches=None, nodes=None, top_k=5, min_score=0.0):
        query_vector = Embedder(self.provider, self.model, self.dimensions, self.profile).embed(query)
        scene_set = set(scenes or [])
        branch_set = set(branches or [])
        node_set = set(nodes or [])
        scored = []

        for document in self.documents:
            record = document.get("record", {})
            meta = record.get("meta", {})
            if scene_set and meta.get("scene") not in scene_set:
                continue
            if branch_set and meta.get("branch") not in branch_set:
                continue
            if node_set and meta.get("node") not in node_set:
                continue

            score = cosine_similarity(query_vector, document.get("vector", []))
            if score > min_score:
                scored.append({
                    "score": round(score, 6),
                    "record_index": document.get("record_index"),
                    "meta": meta,
                    "text": record.get("text", ""),
                })

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]


class Embedder:

    def __init__(self, provider="local-hash", model="", dimensions=384, profile=""):
        self.provider = provider
        self.model = model
        self.dimensions = dimensions
        self.profile = profile

    def embed(self, text):
        if self.provider == "local-hash":
            return local_hash_embedding(text, self.dimensions)
        if self.provider == "openai":
            return openai_embedding(text, self.model or "text-embedding-3-small")
        if self.provider == "compatible":
            return compatible_embedding(text, self.profile, self.model)
        raise ValueError(f"Unsupported embedding provider: {self.provider}")


def local_hash_embedding(text, dimensions=384):
    vector = [0.0] * dimensions
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    return normalize(vector)


def openai_embedding(text, model):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for provider=openai")

    request = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=json.dumps({"model": model, "input": text}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["data"][0]["embedding"]


def compatible_embedding(text, profile_name, model_override=""):
    profile = load_profile(profile_name)
    api_key = profile.get("api_key", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        profile["endpoint"],
        data=json.dumps({
            "model": model_override or profile["model"],
            "input": text,
        }).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["data"][0]["embedding"]


def tokenize(text):
    normalized = re.sub(r"\s+", "", text.lower())
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    chinese_bigrams = [
        "".join(pair)
        for pair in zip(chinese_chars, chinese_chars[1:])
    ]
    words = re.findall(r"[a-z0-9]+", normalized)
    return chinese_chars + chinese_bigrams + words


def cosine_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def normalize(vector):
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]


def _document_text(record):
    meta = record.get("meta", {})
    parts = [
        meta.get("scene", ""),
        meta.get("branch", ""),
        meta.get("node", ""),
        meta.get("actor", ""),
        record.get("text", ""),
    ]
    return "\n".join(part for part in parts if part)
