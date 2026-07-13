import json
import os
import re
from datetime import datetime


class SkillMemory:

    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.data = self._load()

    def learn_command(self, command):
        command = command.strip()
        handlers = (
            self._learn_alias,
            self._learn_preference,
            self._learn_answer_style,
            self._show_memory,
            self._delete_memory,
            self._clear_memory,
        )
        for handler in handlers:
            result = handler(command)
            if result:
                return result
        return None

    def expand_query(self, query):
        expanded = query
        for alias, full_name in self.data.get("aliases", {}).items():
            if alias in expanded and full_name not in expanded:
                expanded = expanded.replace(alias, full_name)
        return expanded

    def apply_query_profile(self, query):
        expanded = self.expand_query(query)
        hints = []
        preferences = self.data.get("preferences", {})

        for key, value in preferences.items():
            if key == "通用" or (key and key in expanded):
                hints.append(f"用户偏好：{key}={value}")

        if hints:
            expanded = f"{expanded}\n\n记忆提示（仅用于理解提问意图，不作为知识事实依据）：\n" + "\n".join(
                f"- {hint}" for hint in hints
            )
        return expanded

    def answer_style(self):
        return self.data.get("defaults", {}).get("answer_style", "")

    def _learn_alias(self, command):
        match = re.match(r"^记住别名[：:]\s*(.+?)\s*[=＝]\s*(.+?)\s*$", command)
        if not match:
            return None
        alias, full_name = (value.strip() for value in match.groups())
        if len(alias) < 2 or len(full_name) < 2:
            return "别名和完整名称至少需要两个字符。"

        self.data.setdefault("aliases", {})[alias] = full_name
        self._audit("add_alias", alias=alias, full_name=full_name)
        self._save()
        return f"已记住检索别名：【{alias}】→【{full_name}】。"

    def _learn_preference(self, command):
        match = re.match(r"^记住偏好[：:]\s*(.+?)\s*[=＝]\s*(.+?)\s*$", command)
        if not match:
            match = re.match(r"^记住偏好[：:]\s*(.+?)\s*$", command)
            if not match:
                return None
            key, value = "通用", match.group(1).strip()
        else:
            key, value = (item.strip() for item in match.groups())
        if len(value) < 2:
            return "偏好内容至少需要两个字符。"
        self.data.setdefault("preferences", {})[key] = value
        self._audit("add_preference", key=key, value=value)
        self._save()
        return f"已记住提问偏好：【{key}】→【{value}】。"

    def _learn_answer_style(self, command):
        match = re.match(r"^记住回答偏好[：:]\s*(.+?)\s*$", command)
        if not match:
            return None
        style = match.group(1).strip()
        if len(style) < 2:
            return "回答偏好至少需要两个字符。"
        self.data.setdefault("defaults", {})["answer_style"] = style
        self._audit("set_answer_style", answer_style=style)
        self._save()
        return f"已记住回答偏好：【{style}】。"

    def _show_memory(self, command):
        if command not in {"查看记忆", "显示记忆", "记忆列表"}:
            return None
        return json.dumps(self._public_memory(), ensure_ascii=False, indent=2)

    def _delete_memory(self, command):
        match = re.match(r"^删除记忆[：:]\s*(别名|偏好|回答偏好)\s*[=＝]\s*(.+?)\s*$", command)
        if not match:
            return None
        category, key = (item.strip() for item in match.groups())
        removed = False
        if category == "别名":
            removed = self.data.setdefault("aliases", {}).pop(key, None) is not None
        elif category == "偏好":
            removed = self.data.setdefault("preferences", {}).pop(key, None) is not None
        elif category == "回答偏好":
            removed = self.data.setdefault("defaults", {}).pop("answer_style", None) is not None
        if not removed:
            return f"未找到可删除的记忆：【{category}={key}】。"
        self._audit("delete_memory", category=category, key=key)
        self._save()
        return f"已删除记忆：【{category}={key}】。"

    def _clear_memory(self, command):
        if command != "清空记忆":
            return None
        self.data = {"aliases": {}, "preferences": {}, "defaults": {}, "audit": []}
        self._audit("clear_memory")
        self._save()
        return "已清空全部非知识事实记忆。"

    def _load(self):
        if not os.path.exists(self.path):
            return {"aliases": {}, "preferences": {}, "defaults": {}, "audit": []}
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = json.load(file)
                data.setdefault("aliases", {})
                data.setdefault("preferences", {})
                data.setdefault("defaults", {})
                data.setdefault("audit", [])
                return data
        except (OSError, json.JSONDecodeError):
            return {"aliases": {}, "preferences": {}, "defaults": {}, "audit": []}

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)

    def _audit(self, action, **payload):
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "action": action,
        }
        entry.update(payload)
        self.data.setdefault("audit", []).append(entry)

    def _public_memory(self):
        return {
            "aliases": self.data.get("aliases", {}),
            "preferences": self.data.get("preferences", {}),
            "defaults": self.data.get("defaults", {}),
        }
