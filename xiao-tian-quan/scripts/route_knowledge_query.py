from difflib import SequenceMatcher
import json
import re


FLOW_TERMS = (
    "流程", "知识流程", "业务流程", "办理流程", "整体流程", "操作流程", "步骤",
    "办理步骤", "操作步骤", "流程图", "流程节点", "多少个条目", "多少个节点",
    "哪些条目", "哪些操作节点", "哪些操作步骤", "责任主体", "操作角色",
    "操作主体", "谁负责", "谁操作", "谁办理", "怎么办理", "如何办理",
)
FLOW_COUNT_TERMS = ("多少个条目", "几个条目", "条目数量", "多少个节点", "几个节点", "节点数量")
FLOW_LIST_TERMS = ("哪些条目", "条目列表", "哪些操作节点", "哪些操作步骤", "流程节点", "操作步骤有")
FLOW_ROLE_TERMS = ("责任主体", "操作角色", "操作主体", "谁负责", "谁操作", "谁办理")
SCENE_NODE_LIST_TERMS = ("有啥条目", "有哪些条目", "什么条目", "条目有哪些", "条目列表", "有啥节点", "有哪些节点", "什么节点", "节点有哪些", "节点列表")
RULE_TERMS = ("知识内容", "规则", "规则内容", "控制点", "限制", "条件", "要求", "能否", "是否允许")
BRANCH_LIST_TERMS = (
    "主题", "主题列表", "有哪些主题", "有啥主题", "什么主题", "几个主题",
    "多少个主题", "主题个数", "主题数量", "业务分支", "场景分支",
    "有哪些分支", "有啥分支", "什么分支", "几个分支", "多少个分支",
    "分支个数", "分支数量",
)
QUERY_FILLERS = (
    "请问", "帮我", "查询", "一下", "知识流程", "业务流程", "办理流程", "整体流程",
    "办理步骤", "怎么办理", "如何办理", "流程", "知识", "业务", "是啥", "是什么",
    "什么样", "怎么", "的", "领域", "主题", "场景", "分支", "有几个主题", "有啥主题", "有哪些主题",
    "几个主题", "多少个主题", "主题个数", "主题数量",
    "有几个分支", "有啥分支", "有哪些分支",
    "几个分支", "多少个分支", "分支个数", "分支数量", "？", "?", "。", " ",
    "总共", "共有", "有多少个节点", "多少个节点", "几个节点", "节点数量",
    "有哪些操作节点", "哪些操作节点", "操作节点", "有哪些操作步骤", "哪些操作步骤",
    "操作步骤", "责任主体", "操作角色", "操作主体", "谁负责", "谁操作", "谁办理", "条目", "节点", "是啥",
    "有啥条目", "有哪些条目", "什么条目", "条目有哪些", "条目列表",
    "有啥节点", "有哪些节点", "什么节点", "节点有哪些", "节点列表",
)


class QueryRouter:

    def __init__(self, rule_records, workflow_records, scene_overviews=None, intent_routes=None):
        self.rule_records = rule_records
        self.workflow_records = workflow_records
        self.scene_overviews = scene_overviews or []
        self.intent_routes = intent_routes or {}
        self.scenes = sorted(
            {record["meta"].get("scene", "") for record in rule_records if record["meta"].get("scene")},
            key=len,
            reverse=True,
        )
        self.branches = sorted(
            {record["meta"].get("branch", "") for record in rule_records if record["meta"].get("branch")},
            key=len,
            reverse=True,
        )
        self.nodes = sorted(
            {record["meta"].get("node", "") for record in rule_records if record["meta"].get("node")},
            key=len,
            reverse=True,
        )

    def route(self, query, intent_hint=None):
        branches = [branch for branch in self.branches if _branch_matches_query(branch, query)]
        nodes = [node for node in self.nodes if _name_matches_query(node, query)]
        scene_query = query
        for branch in branches:
            if branch in scene_query:
                scene_query = scene_query.replace(branch, "")
        scenes = [scene for scene in self.scenes if _name_matches_query(scene, scene_query)]
        route_action = self._custom_route_action(query, intent_hint)
        is_flow_query = route_action == "answer" or intent_hint == "workflow" or any(term in query for term in FLOW_TERMS)
        is_branch_list_query = route_action == "branch_list" or intent_hint in {"topic_list", "scene_branches"} or any(term in query for term in BRANCH_LIST_TERMS)
        is_scene_node_list = route_action == "item_list" or any(term in query for term in SCENE_NODE_LIST_TERMS)

        if is_scene_node_list and scenes:
            return {
                "action": "answer",
                "intent": "workflow",
                "answer": self._format_scene_nodes(scenes, branches),
                "context": {"scene": scenes[0]},
            }

        if is_branch_list_query and scenes:
            overviews = [item for item in self.scene_overviews if item.get("scene") in scenes]
            if overviews:
                return {
                    "action": "branch_list",
                    "intent": "topic_list",
                    "overviews": overviews,
                    "answer": self._format_scene_branches(overviews),
                    "context": {"scene": overviews[0].get("scene", "")},
                }

        if is_branch_list_query:
            suggested_scene = self._best_scene(query)
            if suggested_scene:
                answer = f"未识别到完整领域名称。请确认：您要查询的是【{suggested_scene}】领域的主题列表吗？"
                scenes = [suggested_scene]
            else:
                answer = "请先明确要查询哪个领域的主题列表。"
            return {
                "action": "clarify",
                "intent": "topic_list",
                "answer": answer,
                "pending": {"intent": "branch_list", "query": query, "scenes": scenes},
            }

        if branches and not scenes:
            branch_scenes = self._scenes_for_branches(branches)
            same_name_scenes = [scene for scene in branch_scenes if scene in branches]
            if same_name_scenes:
                scenes = same_name_scenes

        if branches and not scenes:
            scene_options = self._scenes_for_branches(branches)
            return {
                "action": "clarify",
                "intent": "workflow",
                "answer": self._branch_clarification(branches, scene_options),
                "pending": {
                    "intent": "flow" if is_flow_query else "search",
                    "query": query,
                    "scenes": scene_options,
                    "branches": branches,
                },
            }

        if is_flow_query:
            if not branches:
                if not scenes:
                    suggested_scene = self._best_scene(query)
                    if suggested_scene:
                        return {
                            "action": "clarify",
                            "intent": "workflow",
                            "answer": f"未识别到完整领域名称。请确认：您要查询的是【{suggested_scene}】领域的流程吗？",
                            "pending": {
                                "intent": "flow",
                                "query": query,
                                "scenes": [suggested_scene],
                            },
                        }
                branch_options = self._branches_for_scenes(scenes)
                if len(branch_options) == 1:
                    branches = branch_options
                else:
                    return {
                        "action": "clarify",
                        "intent": "workflow",
                        "answer": self._flow_clarification(scenes, branch_options),
                        "pending": {
                            "intent": "flow",
                            "query": query,
                            "scenes": scenes,
                        },
                    }

            workflows = [
                record for record in self.workflow_records
                if record["meta"].get("branch") in branches
                and (not scenes or record["meta"].get("scene") in scenes)
            ]
            if workflows:
                return {
                    "action": "answer",
                    "intent": "workflow",
                    "answer": self._format_workflows(workflows, query),
                    "context": workflows[0].get("meta", {}),
                }

            return {
                "action": "clarify",
                "intent": "workflow",
                "answer": "知识库中已识别领域和主题，但未找到对应的 Mermaid 流程图，请检查该主题文档的【流程图】内容。",
            }

        return {
            "action": "search",
            "intent": "knowledge_rule" if route_action == "search" or intent_hint in {"knowledge_rule", "business_rule"} or any(term in query for term in RULE_TERMS) else "general_search",
            "scenes": scenes,
            "branches": branches,
            "nodes": nodes,
        }

    def _scenes_for_branches(self, branches):
        return sorted({
            record["meta"].get("scene", "")
            for record in self.rule_records
            if record["meta"].get("branch") in branches
        })

    def _branches_for_scenes(self, scenes):
        return sorted({
            record["meta"].get("branch", "")
            for record in self.rule_records
            if not scenes or record["meta"].get("scene") in scenes
        })

    def _best_scene(self, query):
        normalized_query = _normalize_query(query)
        if len(normalized_query) < 2:
            return ""

        def score(scene):
            sequence_score = SequenceMatcher(None, normalized_query, scene).ratio()
            overlap = len(set(normalized_query) & set(scene)) / max(len(set(normalized_query)), 1)
            return sequence_score * 0.7 + overlap * 0.3

        best_scene = max(self.scenes, key=score, default="")
        return best_scene if best_scene and score(best_scene) >= 0.35 else ""

    def _custom_route_action(self, query, intent_hint):
        route = self.intent_routes.get(intent_hint or "")
        if route:
            return route.get("action", "")
        for route in self.intent_routes.values():
            if any(keyword and keyword in query for keyword in route.get("keywords", [])):
                return route.get("action", "")
        return ""

    def _branch_clarification(self, branches, scenes):
        branch_text = "、".join(f"【{branch}】" for branch in branches)
        scene_text = "、".join(f"【{scene}】" for scene in scenes)
        if len(scenes) == 1:
            return f"请确认：您询问的是{scene_text}领域下的{branch_text}主题吗？请在问题中补充领域名称。"
        return f"您提到了{branch_text}主题，请补充所属领域。可选领域：{scene_text}。"

    def _flow_clarification(self, scenes, branches):
        scene_text = "、".join(f"【{scene}】" for scene in scenes) or "该领域"
        branch_text = "、".join(f"【{branch}】" for branch in branches)
        return f"请明确要查询{scene_text}下的哪个主题流程。可选主题：{branch_text}。"

    def _format_workflows(self, workflows, query):
        return "\n\n---\n\n".join(self._format_workflow(record, query) for record in workflows)

    def _format_scene_branches(self, overviews):
        answers = []
        for overview in overviews:
            branches = overview.get("branches", [])
            lines = [
                f"所属领域：{overview.get('scene', '')}",
                "",
                f"该领域共包含 {len(branches)} 个主题，分别为：",
            ]
            lines.extend(
                f"{index}. {branch.replace(chr(10), '')}"
                for index, branch in enumerate(branches, start=1)
            )
            answers.append("\n".join(lines))
        return "\n\n---\n\n".join(answers)

    def _format_scene_nodes(self, scenes, branches):
        grouped_nodes = {}
        for record in self.rule_records:
            meta = record.get("meta", {})
            if meta.get("scene") not in scenes:
                continue
            if branches and meta.get("branch") not in branches:
                continue
            branch = meta.get("branch", "未标注主题")
            node = meta.get("node", "")
            if node and node not in grouped_nodes.setdefault(branch, []):
                grouped_nodes[branch].append(node)

        lines = ["基础信息", f"所属领域：{'、'.join(scenes)}", "", "条目列表"]
        for branch_index, (branch, nodes) in enumerate(grouped_nodes.items(), start=1):
            lines.append(f"{branch_index}、{branch}")
            lines.extend(f"  {index}. {node}" for index, node in enumerate(nodes, start=1))
            lines.append("")
        return "\n".join(lines).strip()

    def _format_workflow(self, workflow, query):
        meta = workflow["meta"]
        node_names, node_actors, edges = _parse_mermaid(workflow["text"])
        ordered_ids = _ordered_node_ids(node_names, edges)
        rule_map = self._rule_map(meta.get("scene", ""), meta.get("branch", ""))
        lines = [
            "基础信息",
            f"所属领域：{meta.get('scene', '')}",
            f"所属主题：{meta.get('branch', '')}",
            "",
            "流程",
        ]

        if any(term in query for term in FLOW_COUNT_TERMS):
            lines.append(f"该流程共包含 {len(ordered_ids)} 个条目。")
            return "\n".join(lines)

        if any(term in query for term in FLOW_ROLE_TERMS):
            matched_ids = [node_id for node_id in ordered_ids if node_names[node_id] in query]
            if matched_ids:
                for node_id in matched_ids:
                    node = node_names[node_id]
                    actor = node_actors.get(node_id, "未标注")
                    lines.append(f"【{node}】条目的责任主体是【{actor}】。")
                return "\n".join(lines)

        if any(term in query for term in FLOW_LIST_TERMS):
            for index, node_id in enumerate(ordered_ids, start=1):
                lines.append(f"{index}. 【{node_actors.get(node_id, '未标注')}】{node_names[node_id]}")
            return "\n".join(lines)

        for index, node_id in enumerate(ordered_ids, start=1):
            node = node_names[node_id]
            actor = node_actors.get(node_id, "未标注")
            summary = rule_map.get(node) or f"由{actor}完成“{node}”处理。"
            lines.append(f"{index}. 【{actor}】{node}：{summary}")

        return "\n".join(lines)

    def _rule_map(self, scene, branch):
        rules = {}
        for record in self.rule_records:
            meta = record["meta"]
            if meta.get("scene") != scene or meta.get("branch") != branch:
                continue
            _, _, rule = record["text"].partition("知识内容：")
            if not rule:
                _, _, rule = record["text"].partition("规则：")
            first_rule = next((line.strip() for line in rule.splitlines() if line.strip()), "")
            first_rule = re.sub(r"^\d+[.、．]\s*", "", first_rule)
            if first_rule:
                rules[meta.get("node", "")] = first_rule
        return rules


def _parse_mermaid(mermaid):
    node_names = {}
    node_actors = {}
    edges = []
    actor = ""

    for raw_line in mermaid.splitlines():
        line = raw_line.strip()
        subgraph_match = re.match(r"subgraph\s+(.+)", line)
        if subgraph_match:
            actor = subgraph_match.group(1).strip()
            continue
        if line == "end":
            actor = ""
            continue

        node_match = re.match(r"([A-Za-z0-9_]+)\[([^]]+)\]", line)
        if node_match:
            node_id, node_name = node_match.groups()
            node_names[node_id] = node_name
            node_actors[node_id] = actor

        edge_ids = re.findall(r"([A-Za-z0-9_]+)\s*-->", line)
        edge_end = re.search(r"-->\s*([A-Za-z0-9_]+)", line)
        if edge_ids and edge_end:
            edges.append((edge_ids[-1], edge_end.group(1)))

    return node_names, node_actors, edges


def _ordered_node_ids(node_names, edges):
    if not edges:
        return list(node_names)

    next_nodes = {source: target for source, target in edges}
    targets = {target for _, target in edges}
    start = next((source for source, _ in edges if source not in targets), edges[0][0])
    ordered = []
    seen = set()
    current = start

    while current in node_names and current not in seen:
        ordered.append(current)
        seen.add(current)
        current = next_nodes.get(current)

    ordered.extend(node_id for node_id in node_names if node_id not in seen)
    return ordered


def _name_matches_query(name, query):
    if name in query:
        return True

    phrases = [query] + re.split(r"[，,。！？?；;]", query)
    for phrase in phrases:
        normalized_query = phrase
        for filler in sorted(QUERY_FILLERS, key=len, reverse=True):
            normalized_query = normalized_query.replace(filler, "")
        normalized_query = normalized_query.strip()
        if len(normalized_query) >= 4 and (
            normalized_query in name or _is_subsequence(normalized_query, name)
        ):
            return True
    return False


def _branch_matches_query(branch, query):
    if _name_matches_query(branch, query):
        return True
    return any(
        len(part.strip()) >= 4 and part.strip() in query
        for part in re.split(r"[/、]", branch)
    )


def _normalize_query(query):
    normalized = query
    for filler in sorted(QUERY_FILLERS, key=len, reverse=True):
        normalized = normalized.replace(filler, "")
    return re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]", "", normalized)


def _is_subsequence(short_name, full_name):
    characters = iter(full_name)
    return all(character in characters for character in short_name)


def load_intent_routes(path):
    if not path:
        return {}
    with open(path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    routes = data.get("routes", data)
    return {
        name: {
            "action": route.get("action", "search"),
            "keywords": route.get("keywords", []),
        }
        for name, route in routes.items()
        if isinstance(route, dict)
    }
