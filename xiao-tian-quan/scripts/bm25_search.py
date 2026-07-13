import json
import math
import re
from collections import Counter
from pathlib import Path


class BM25Index:

    def __init__(self, documents, idf, avg_doc_length, k1=1.5, b=0.75):
        self.documents = documents
        self.idf = idf
        self.avg_doc_length = avg_doc_length
        self.k1 = k1
        self.b = b

    @classmethod
    def from_records(cls, records):
        documents = []
        document_frequency = Counter()

        for index, record in enumerate(records):
            text = _document_text(record)
            tokens = tokenize(text)
            token_counts = Counter(tokens)
            documents.append({
                "record_index": index,
                "text": text,
                "tokens": dict(token_counts),
                "length": len(tokens),
                "record": record,
            })
            document_frequency.update(set(tokens))

        total_documents = len(documents)
        idf = {
            token: math.log(1 + (total_documents - count + 0.5) / (count + 0.5))
            for token, count in document_frequency.items()
        }
        avg_doc_length = (
            sum(document["length"] for document in documents) / total_documents
            if total_documents else 0
        )
        return cls(documents, idf, avg_doc_length)

    @classmethod
    def load(cls, path):
        with Path(path).open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
        return cls(
            data.get("documents", []),
            data.get("idf", {}),
            data.get("avg_doc_length", 0),
            data.get("k1", 1.5),
            data.get("b", 0.75),
        )

    def save(self, path):
        data = {
            "version": 1,
            "k1": self.k1,
            "b": self.b,
            "avg_doc_length": self.avg_doc_length,
            "idf": self.idf,
            "documents": self.documents,
        }
        with Path(path).open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def search(self, query, scenes=None, branches=None, nodes=None, top_k=5):
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

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

            score = self._score_document(query_tokens, document)
            if score > 0:
                scored.append({
                    "score": round(score, 6),
                    "record_index": document.get("record_index"),
                    "meta": meta,
                    "text": record.get("text", ""),
                })

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def _score_document(self, query_tokens, document):
        score = 0.0
        token_counts = document.get("tokens", {})
        doc_length = document.get("length", 0)
        length_norm = self.k1 * (1 - self.b + self.b * doc_length / max(self.avg_doc_length, 1))

        for token in query_tokens:
            frequency = token_counts.get(token, 0)
            if not frequency:
                continue
            score += self.idf.get(token, 0) * frequency * (self.k1 + 1) / (frequency + length_norm)
        return score


def tokenize(text):
    normalized = re.sub(r"\s+", "", text.lower())
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    chinese_bigrams = [
        "".join(pair)
        for pair in zip(chinese_chars, chinese_chars[1:])
    ]
    words = re.findall(r"[a-z0-9]+", normalized)
    return chinese_chars + chinese_bigrams + words


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
