---
name: xiao-tian-quan
description: 解析、构建和查询使用 Markdown 编写的通用知识库，支持统一索引目录、查询前自动索引检查与重建、FAISS 向量索引、embedding 线性检索、BM25 词法召回、可配置意图路由、非事实记忆和集中维护调试说明。使用场景包括：把任意领域文档按领域、主题、条目和知识内容提取为结构化记录；把 Mermaid 流程、主题概览和知识条目生成到同一 records JSON；按自定义意图关键词路由到主题列表、流程答案、澄清问题或知识检索；在结构化精确匹配不足时自动选择 semantic、lexical 或 hybrid 检索策略；根据当前线程上下文处理多轮指代；按用户明确指令记住检索别名、提问偏好和回答偏好，但记忆不得作为知识库事实依据。
---

# 哮天犬

先按文档结构定位领域、主题和条目，再依据自定义意图路由查询知识内容。主题、流程和知识事实以 Markdown 原文为准；精确匹配不足时，使用检索补充召回。

## 查询流程

1. 适配新知识库或排查解析问题时，读取 `references/document-format.md`。
2. 运行 `python scripts/extract_knowledge_md.py <文档目录> > knowledge_records.json`，导出 `rules`、`workflows` 和 `scene_overviews`。
3. 普通对话查询时，用户只输入自然语言问题；智能体调用查询脚本时默认使用 `knowledge_records.json`、`--index-dir indexes`、`--retrieval auto` 和 `--max-rule-chars 5000`。
4. 如果调用环境配置了 `--docs-dir <文档目录>`，查询入口会先从 Markdown 文档刷新 `knowledge_records.json`，再检查 `indexes/index_manifest.json`。
5. 如果索引目录不存在、manifest 缺失或 records 指纹变化，查询入口会自动运行统一建索引逻辑并重建 FAISS、embedding、BM25。
6. 默认使用内置意图关键词；如需扩展领域意图，传入 `--intent-routes <路由JSON>`。
7. 路由结果为 `search` 时，先根据问题选择检索策略，再在已确认的领域、主题和条目范围内召回知识内容。
8. 如果问题是记忆管理命令，通过 `scripts/skill_memory.py` 写入或读取 skill 目录下的 `data/memory/retrieval_skills.json` 并直接返回确认。
9. 普通问题先用技能记忆扩展别名并附加提问偏好提示；记忆只帮助理解提问意图，不作为知识事实依据。
10. 回答时保留命中的 `scene、branch、node、actor` 兼容字段；在通用语义中分别表示领域、主题、条目和责任主体。

## 自定义意图路由

- 默认支持 `topic_list`、`workflow`、`knowledge_rule` 和 `general_search`。
- 外部路由 JSON 可按意图名配置 `action` 和 `keywords`；`action` 支持 `branch_list`、`answer`、`item_list` 和 `search`。
- 可从 `references/intent_routes.template.json` 复制模板到知识库目录，按具体领域改写 `keywords`。
- 示例：

```json
{
  "routes": {
    "policy_scope": {
      "action": "search",
      "keywords": ["适用范围", "覆盖对象", "适用于"]
    },
    "chapter_list": {
      "action": "branch_list",
      "keywords": ["有哪些章节", "章节列表", "几个模块"]
    },
    "handling_steps": {
      "action": "answer",
      "keywords": ["处理步骤", "执行流程", "怎么处理"]
    }
  }
}
```

- `branch_list` 从 `scene_overviews` 的主题概览读取列表，不从向量候选推断。
- `answer` 优先读取对应主题的 Mermaid 流程。
- `search` 先做领域、主题、条目精确限定，再根据问题选择 `semantic`、`lexical` 或 `hybrid` 召回。
- 如果用户问题缺少必要领域或主题，先返回 `clarify`，不要提前进入向量检索。

## 索引同步

- 使用 `--docs-dir <文档目录> --index-dir indexes` 查询时，文档内容补充或更新后会自动刷新 `knowledge_records.json`，并在索引过期时自动重建。
- 如果查询时不传 `--docs-dir`，脚本只能检查当前 `knowledge_records.json` 与索引是否一致，不能直接感知 Markdown 原文是否变化。
- `build_all_indexes.py` 会写入 `indexes/index_manifest.json`，记录当前 `knowledge_records.json` 的 `records_fingerprint`。
- 查询时传入 `--index-dir indexes` 会检查 records 指纹、构建配置及实际索引文件；任一不一致时，默认 `--auto-index` 会自动重建。
- 可单独运行 `python scripts/check_index_freshness.py knowledge_records.json indexes` 检查索引是否过期；退出码为 `0` 表示新鲜，`1` 表示需要重建。
- 如需关闭自动重建，传入 `--no-auto-index`。

## AI 向量配置

- 通用向量 API 配置位于 `scripts/provider_config.py`。
- 使用支持 OpenAI `/embeddings` 响应格式的云端或本地服务时，运行查询命令并传入 `--provider compatible --profile <配置名>`。
- 聊天模型接口不能代替 embedding 接口。
- API Key 优先从配置项指定的环境变量读取；受运行环境限制时可以临时写入 profile 的 `api_key`，但不得写入 `SKILL.md`、索引文件或公开仓库。

## 维护调试

- 普通对话用户不要输入 `--retrieval`、`--index-dir`、`--docs-dir`、`--provider` 等命令行参数；这些参数由智能体或维护人员在调用脚本时配置。
- 手动查询默认命令：`python scripts/query_knowledge_base.py knowledge_records.json "<用户问题>" --docs-dir <文档目录> --index-dir indexes --retrieval auto --max-rule-chars 5000`。
- 使用自定义意图路由：`python scripts/query_knowledge_base.py knowledge_records.json "<用户问题>" --intent-routes intent_routes.json --index-dir indexes --retrieval auto`。
- 检查索引是否新鲜：`python scripts/check_index_freshness.py knowledge_records.json indexes`。
- 手动重建全部索引：`python scripts/build_all_indexes.py knowledge_records.json indexes`。
- 强制语义检索：在手动查询命令中加入 `--retrieval semantic`；适合原因、能否、异常处理和相近表达问题。
- 强制关键词检索：在手动查询命令中加入 `--retrieval lexical`；适合原文、编号、字段、名称、明确条目名问题。
- 强制混合检索：在手动查询命令中加入 `--retrieval hybrid`；适合同时包含明确关键词和语义判断的问题。
- 完整输出长内容：在手动查询命令中加入 `--max-rule-chars 0`。
- 默认记忆文件固定在本 skill 目录的 `data/memory/retrieval_skills.json`；如需临时改到其他位置，手动查询时传入 `--memory-dir <目录>`。

## 问题理解与逐步澄清

1. 先识别当前问题中显式出现的领域、主题和条目；本轮显式信息优先级高于当前线程上下文。
2. 只有当前问题缺少必要信息时，才结合当前线程上下文理解“这个条目、该主题、继续、是的”等指代；技能不保存本地对话历史文件。
3. 如果用户本轮切换到其他领域、主题或条目，立即以本轮目标为准，不要沿用上一轮命中的上下文。
4. 能直接理解时，生成保留原意的完整查询问题，并补入必要的领域、主题或条目。
5. 无法确定唯一目标时，只提出一个最关键的澄清问题。
6. 用户补充信息后，将补充内容与原问题合并，再重新进入路由。

## 查询与回答要求

- 不得增加原文不存在的条件、角色、流程或结论。
- 润色和分类规整时不得改变原文知识含义。
- 合并或分类知识条目时，确保每条来源内容都被覆盖且只出现一次。
- 知识内容较多时，可以修正语病、润色表达、分组分类和整理条目顺序，但不得概括压缩、遗漏、合并不同条目或删除限制条件。
- 回答主题列表时，根据中文并列结构补全被省略的共同主体、对象或动作词，使每个主题名称都能独立理解；不得新增、删除或合并主题。
- 回答知识内容前展示所属领域、所属主题、所属条目和责任主体。
- 使用清晰的中文编号和重点名称，不要输出 `###` 等 Markdown 解析标记。
- 查询资料与问题不匹配时，回答 `知识库中未找到准确依据`。

## 答案优化层

1. 先完成确定性的领域、主题、流程或知识内容检索，再调用大模型优化表达；不要让大模型代替检索。
2. 主题列表答案可补全并列名称中的省略词，但必须通过来源记录校验后再渲染。
3. Mermaid 流程答案先由程序解析主体、条目和顺序，再交给大模型优化为清晰、明确、结构化的中文答案。
4. 完整流程优化时保留全部条目和原始顺序；数量、列表和主体问题只回答对应内容。
5. 知识内容优化时只做语病修正、表达润色、分类归并和条目清晰化，不得把多条内容压缩成摘要。
6. 大模型不得新增、删除或改变知识事实，不得输出资料编号、相关度、`###` 或 Mermaid 原始代码。
7. 大模型调用失败、输出为空或包含无关资料标记时，回退到确定性原始答案。

## 记忆使用规则

- 记忆只用于理解提问意图、扩展别名和控制回答偏好，不得作为知识事实依据。
- 支持 `记住别名：简称=完整名称`，用于把用户常用简称扩展为知识库中的完整名称。
- 支持 `记住偏好：关键词=偏好说明` 或 `记住偏好：偏好说明`，用于理解用户表达习惯。
- 支持 `记住回答偏好：偏好说明`，只影响答案组织形式，不改变知识事实。
- 支持 `查看记忆`、`删除记忆：别名=简称`、`删除记忆：偏好=关键词`、`删除记忆：回答偏好=任意值` 和 `清空记忆`。
- 不要把“某规则成立、某材料不用提交、某条目无需审核”等知识事实写入记忆；这类内容必须更新 Markdown 知识库原文。

## 技能优化

- 只有用户明确输入支持的记忆管理命令时，才写入技能记忆。
- 不要根据未经确认的回答自动修改知识库原文、提示词或程序代码。
