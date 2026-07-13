import re

def split_md(content):

    return [record["text"] for record in split_md_records(content)]


def split_md_records(content, file_name=""):

    """
    按文档 -> 领域 -> 主题 -> 条目抽取 Markdown 知识块。
    """

    records = []
    scene_name = extract_any(content, ("领域名称", "场景名称"))
    pattern = re.compile(r"^### \[(.*?)\] ###\s*$", re.MULTILINE)
    matches = list(pattern.finditer(content))

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        node = content[start:end].strip()

        if len(node) < 20:
            continue

        scene = extract_any(node, ("所属领域", "所属场景"))
        branch = extract_any(node, ("所属主题", "所属分支"))
        action = extract_any(node, ("所属条目", "所属节点")) or match.group(1).strip()
        actor = extract_any(node, ("责任主体", "操作主体"))
        rule = extract_any(node, ("知识内容", "业务规则", "规则内容"))

        if _is_empty_rule(rule):
            continue

        scene = scene or scene_name
        chunk = f"""
文档：{file_name}
领域：{scene}
主题：{branch}
条目：{action}
责任主体：{actor}
知识内容：{rule}
""".strip()

        records.append({
            "text": chunk,
            "meta": {
                "file_name": file_name,
                "scene": scene,
                "branch": branch,
                "node": action,
                "actor": actor,
            }
        })

    return records


def split_workflow_records(content, file_name=""):
    records = []
    pattern = re.compile(
        r"^##[ \t]+((?:(?!^##).)*?)(?:流程|业务流程)[ \t]*##[ \t]*$",
        re.MULTILINE | re.DOTALL,
    )
    matches = list(pattern.finditer(content))

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        next_section = re.search(r"^##\s+", content[start:end], re.MULTILINE)
        if next_section:
            end = start + next_section.start()

        section = content[start:end].strip()
        mermaid_match = re.search(r"```mermaid\s*(.*?)```", section, re.DOTALL)
        if mermaid_match:
            mermaid_text = mermaid_match.group(1).strip()
        else:
            plain_mermaid = re.search(r"^(?:flowchart|graph)\s+.*\Z", section, re.MULTILINE | re.DOTALL)
            if not plain_mermaid:
                continue
            mermaid_text = plain_mermaid.group(0).strip()

        scene = extract_any(section, ("所属领域", "所属场景")) or extract_any(content, ("领域名称", "场景名称"))
        branch = extract_any(section, ("所属主题", "所属分支")) or match.group(1).strip()
        records.append({
            "text": mermaid_text,
            "meta": {
                "file_name": file_name,
                "scene": scene,
                "branch": branch,
                "type": "workflow",
            },
        })

    return records


def extract_scene_overview(content, file_name=""):
    headings = list(re.finditer(r"^#(?!#)(?:\s+.*)?$", content, re.MULTILINE))
    end = headings[1].start() if len(headings) > 1 else len(content)
    overview = content[:end]
    scene = _extract_overview_field_any(overview, ("领域名称", "场景名称"))
    branch_text = _extract_overview_field_any(overview, ("主题名称", "场景分支名称", "分支名称"))
    return {
        "file_name": file_name,
        "scene": scene,
        "branches": [item.strip() for item in branch_text.split("、") if item.strip()],
        "branch_text": branch_text,
    }


def extract(text, key):

    pattern = rf"【{re.escape(key)}】：\s*(.*?)(?=\n【[^】]+】：|\n### |\Z)"
    match = re.search(pattern, text, re.DOTALL)

    if match:
        return match.group(1).strip()

    return ""


def extract_any(text, keys):
    for key in keys:
        value = extract(text, key)
        if value:
            return value
    return ""


def _is_empty_rule(rule):
    if not rule or len(rule.strip()) < 2:
        return True

    normalized = re.sub(r"^\s*\d+[.、．]\s*", "", rule.strip())
    normalized = normalized.strip().lower()

    return normalized in {"nan", "none", "null"}


def _extract_overview_field(text, key):
    pattern = rf"【{re.escape(key)}】：\s*(.*?)(?=\n【[^】]+】：|\n#|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_overview_field_any(text, keys):
    for key in keys:
        value = _extract_overview_field(text, key)
        if value:
            return value
    return ""
