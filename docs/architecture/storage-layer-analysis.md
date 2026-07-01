# PowerMem 存储层架构分析与扩展方案

> 分析日期：2026-07-02
> 分析范围：存储后端实现、混合搜索能力、外部项目适配性

## 1. 存储层整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Memory (SDK 入口)                          │
│              src/powermem/core/memory.py                      │
├─────────────────────────────────────────────────────────────┤
│                    StorageAdapter                            │
│              src/powermem/storage/adapter.py                 │
│    ┌──────────────────────────────────────────────────────┐  │
│    │  VectorStoreFactory          GraphStoreFactory       │  │
│    │  (注册表模式，动态加载后端)    (同上)                   │  │
│    └──────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│              后端实现 (通过 class_path 动态加载)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │OceanBase │ │ pgvector │ │ SQLite   │ │ Embedded     │   │
│  │(远程集群) │ │          │ │          │ │ SeekDB       │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
├─────────────────────────────────────────────────────────────┤
│              附加存储层                                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐    │
│  │ Graph Store  │ │ Skill Store  │ │ Source Store     │    │
│  │ (OceanBase)  │ │ (OceanBase)  │ │ (OceanBase)      │    │
│  └──────────────┘ └──────────────┘ └──────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 核心抽象

**`VectorStoreBase`** (`src/powermem/storage/base.py:18`) 定义了所有向量存储后端必须实现的接口：

| 方法 | 说明 |
|------|------|
| `create_col(name, vector_size, distance)` | 创建集合 |
| `insert(vectors, payloads, ids)` | 插入向量 |
| `search(query, vectors, limit, filters)` | 搜索 |
| `delete/update/get` | CRUD |
| `list` | 分页列表 |
| `get_statistics/get_unique_users` | 统计 |

**`GraphStoreBase`** (`src/powermem/storage/base.py:101`) 定义图存储接口：

| 方法 | 说明 |
|------|------|
| `add(data, filters)` | 添加实体和关系 |
| `search(query, filters, limit)` | 图搜索（多跳遍历） |
| `delete_all/get_all/reset` | 图管理 |

### 后端选择机制

`platform_defaults.py:136` 的 `choose_default_database_provider()` 决定默认后端：

```python
# 优先级从高到低：
1. DATABASE_PROVIDER 环境变量 → 使用指定值
2. OCEANBASE_HOST 已配置 → 使用远程 OceanBase
3. 嵌入式 SeekDB 可用（Linux + pyobvector + pyseekdb）→ 使用 OceanBase 模式
4. 以上都不满足 → 使用 SQLite（功能受限）
```

## 2. 四种存储后端详解

### 2.1 OceanBase（远程集群）

**文件**：`src/powermem/storage/oceanbase/oceanbase.py`

**特点**：
- 通过 `ObVecClient` 连接远程 OceanBase 集群
- 支持原生混合搜索（vector + fulltext + sparse）
- 使用 SQLAlchemy + `pyobvector` SDK
- 表结构：`id`（Snowflake ID）、`embedding`（VECTOR）、`fulltext_content`（LONGTEXT）、`metadata`（JSON）、`sparse_embedding`（SPARSE_VECTOR）
- 支持向量索引：HNSW、IVF_FLAT、IVF_PQ、FLAT
- 支持全文索引：ngram、jieba 等分词器

**搜索模式**：

| 模式 | 说明 |
|------|------|
| `auto` | 混合搜索（vector + FTS） |
| `vector` | 纯向量搜索 |
| `fts` | 纯全文搜索 |
| `hybrid` | 显式混合搜索 |

**融合方法**：

| 方法 | 说明 |
|------|------|
| `rrf` | Reciprocal Rank Fusion（默认） |
| `weighted` | 加权融合 |

### 2.2 Embedded SeekDB（嵌入式）

**文件**：同 OceanBase（`oceanbase.py`）

**关键区别**：
- 无 host 时自动切换为嵌入式模式
- 使用 `ObVecClient(path=ob_path, db_name=db_name)` 连接本地嵌入式数据库
- 数据存储在 `./seekdb_data` 目录
- IVF 索引在小数据集上自动切换为 HNSW

**SeekDB 限制**：

| 限制 | 说明 |
|------|------|
| Graph Store 不可用 | 需要完整 OceanBase |
| sub_stores 路由不可用 | |
| Sparse vector 不可用 | |
| SkillStore 不可用 | 需要 OceanBase 或嵌入式 SeekDB |

### 2.3 pgvector（PostgreSQL）

**文件**：`src/powermem/storage/pgvector/pgvector.py`

**特点**：
- 支持 psycopg2 和 psycopg3（自动检测）
- 使用连接池
- 表结构：`id`（BIGINT）、`vector`（vector(N)）、`payload`（JSONB）、`fulltext_content`（TEXT）
- 支持 HNSW 和 DiskANN（需 `vectorscale` 扩展）

**混合搜索**（2026-07-02 新增）：

| 能力 | 说明 |
|------|------|
| FTS 搜索 | 基于 `tsvector/tsquery`，支持 GIN 索引 |
| RRF 融合 | Reciprocal Rank Fusion |
| 加权融合 | Min-max 归一化 + 加权求和 |
| 并发执行 | ThreadPoolExecutor 并发向量 + FTS 搜索 |
| 阈值过滤 | 基于 quality_score 过滤 |

### 2.4 SQLite

**文件**：`src/powermem/storage/sqlite/sqlite_vector_store.py`

**特点**：
- 零依赖，适合开发和测试
- 向量存储为 JSON 字符串，应用层计算余弦相似度
- 使用 FTS5 虚拟表实现全文搜索
- 支持 WAL 模式

**SQLite 限制**：

| 限制 | 说明 |
|------|------|
| 无 Graph Store | |
| 无 sub_stores 路由 | |
| 无 Sparse vector | |
| SkillStore 不可用 | |

## 3. 混合搜索实现对比

### 3.1 pgvector 混合搜索（新增）

```python
# 实现方式：应用层 RRF 融合
def search(query, vectors, limit, filters, retrieval_mode="auto"):
    if mode == "fts":
        return _fulltext_search(query, limit, filters)
    if mode == "vector" or not has_query:
        return _vector_search(vectors, limit, filters)

    # 并发执行向量 + FTS 搜索
    with ThreadPoolExecutor(max_workers=2) as executor:
        vector_future = executor.submit(_vector_search, ...)
        fts_future = executor.submit(_fulltext_search, ...)

    # RRF 融合
    return _rrf_fusion(vector_results, fts_results, limit)
```

**FTS 实现**：
```sql
-- GIN 索引
CREATE INDEX {collection}_fts_idx ON {collection}
USING GIN (to_tsvector('{language}', fulltext_content));

-- 搜索
SELECT id, payload,
       ts_rank(to_tsvector('{language}', fulltext_content),
               to_tsquery('{language}', %s)) AS rank
FROM {collection}
WHERE to_tsvector('{language}', fulltext_content) @@ to_tsquery('{language}', %s)
ORDER BY rank DESC LIMIT %s;
```

### 3.2 OceanBase 混合搜索

```python
# 三层混合搜索能力

# 1. 应用层混合搜索（_hybrid_search）
# 并发执行 3 路搜索（vector + fulltext + sparse）
# RRF 或 weighted 融合
# 可选 Reranker 精排

# 2. 原生混合搜索（_native_hybrid_search）
# 使用 OceanBase 内置的 DBMS_HYBRID_SEARCH.SEARCH
# 数据库内核级融合，单次 SQL 完成

# 3. 自适应权重归一化
# _normalize_weights_adaptively()
# 动态调整权重解决混合状态下的公平性问题
```

**原生搜索 SQL**：
```sql
SELECT DBMS_HYBRID_SEARCH.SEARCH(:index, :body_str)
-- body_str 包含 query、rank.rrf、knn 参数
```

### 3.3 差距对比表

| 维度 | pgvector | OceanBase |
|------|----------|-----------|
| **混合搜索** | 2 路并发 + RRF/weighted | 3 路并发 + RRF/weighted |
| **全文搜索** | tsvector/tsquery | 原生 FTS（ngram/jieca） |
| **Sparse Vector** | 不支持 | 原生 SPARSE_VECTOR |
| **数据库级融合** | 无 | DBMS_HYBRID_SEARCH.SEARCH |
| **Reranker** | 不支持 | 内置 `_apply_rerank` |
| **过滤+向量联合** | JSONB 过滤 | 列级过滤 + 向量索引 |
| **自适应权重** | 无 | `_normalize_weights_adaptively` |
| **Graph Store** | 不支持（可集成 AGE） | 原生图存储 |
| **Skill Store** | 不支持 | 原生技能存储 |

## 4. 外部项目适配性分析

### 4.1 SAG（Structural Event-Centric Retrieval）

**项目位置**：`D:\dev\lawgraph\SAG`

**是什么**：事件驱动的 RAG 系统，将文档知识组织为 `chunk → event`、`chunk → entities`、`event ↔ entities` 的图结构。

**技术栈**：TypeScript（Fastify + React）、PostgreSQL + pgvector、MCP 协议

**与 PowerMem 的适配性**：

| 维度 | 适配性 | 说明 |
|------|--------|------|
| 存储后端 | 高 | 都用 PostgreSQL + pgvector |
| MCP 协议 | 高 | SAG 提供 MCP server |
| LLM 接口 | 高 | 都用 OpenAI 兼容 API |
| 图结构 | 中 | SAG 的 event-entity 图可补充 PowerMem |
| 语言 | 低 | TypeScript vs Python |

**集成方案**：

1. **MCP 协议集成**：PowerMem 通过 MCP 协议调用 SAG 的 `sag_search` 工具
2. **共享数据库**：SAG 和 PowerMem 共用 PostgreSQL + pgvector
3. **分工**：SAG 负责事件/实体提取和多跳图检索，PowerMem 负责记忆生命周期管理

**SAG MCP 工具**：
- `sag_ingest_document` — 文档摄入
- `sag_search` — 搜索
- `sag_explain_search` — 解释搜索结果
- `sag_get_event` — 获取事件详情

### 4.2 Apache AGE

**项目位置**：`D:\dev\lawgraph\age-source`

**是什么**：PostgreSQL 的图数据库扩展，在 PostgreSQL 上提供 openCypher 查询语言。

**技术栈**：C 扩展、PostgreSQL 11-18、Bison/Flex 解析器、Python/Go/Java/Node 驱动

**与 PowerMem 的适配性**：

| 维度 | 适配性 | 说明 |
|------|--------|------|
| 存储共享 | 高 | AGE 和 pgvector 可共存于同一 PostgreSQL |
| 图能力 | 高 | AGE 提供原生 Cypher 查询 |
| Python 驱动 | 高 | `drivers/python/` 可直接被 PowerMem 调用 |
| pgvector 共存 | 高 | `enable_vector.sql` 证明两者可协同 |
| 部署复杂度 | 低 | 需要编译 C 扩展 |

**集成方案**：

1. 在 PostgreSQL 上同时安装 AGE 和 pgvector 扩展
2. PowerMem 的 pgvector 后端负责向量存储和搜索
3. AGE 负责图存储和 Cypher 查询
4. 通过 Python 驱动桥接两者

**AGE Python 驱动用法**：
```python
import age
conn = age.connect(host='localhost', port=5432, dbname='graph_db')
# 执行 Cypher 查询
result = conn.execute("MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 10")
```

### 4.3 PowerMem TypeScript SDK

**文档参考**：`docs/PowerMem-SDKtoTypeScript.md`

**关键发现**：PowerMem 已有 TypeScript SDK（`ob-labs/powermem-ts`），核心能力已对齐 98%。

**对 SAG 集成的意义**：
- TypeScript SDK 可作为 SAG 集成的桥梁
- 通过 HTTP API 或 MCP 协议，TypeScript 客户端可调用 PowerMem 后端
- 无需跨语言调用，直接通过网络协议通信

## 5. 推荐集成路径

### 5.1 最短路径：pgvector + AGE

在 PostgreSQL 生态内补齐图能力：

```
PowerMem
├── pgvector 向量存储 + FTS（已实现混合搜索）
├── AGE 扩展 图存储 + Cypher 查询
└── Python 驱动 桥接两者
```

**需要做的工作**：
1. ✅ 给 `PGVectorStore` 添加混合搜索（已完成）
2. 新增 `AGEGraphStore` 实现 `GraphStoreBase` 接口
3. 通过 AGE Python 驱动执行 Cypher 查询

### 5.2 最强路径：OceanBase 原生

保持当前架构，OceanBase 提供一站式能力。

### 5.3 中间路径：PowerMem + SAG MCP

通过 MCP 协议调用 SAG 的事件图检索能力，不修改 PowerMem 核心。

## 6. 实现状态

| 组件 | 状态 | 文件 |
|------|------|------|
| pgvector 混合搜索 | ✅ 已实现 | `src/powermem/storage/pgvector/pgvector.py` |
| pgvector FTS GIN 索引 | ✅ 已实现 | `create_col()` |
| pgvector RRF 融合 | ✅ 已实现 | `_rrf_fusion()` |
| pgvector 加权融合 | ✅ 已实现 | `_weighted_fusion()` |
| pgvector 并发搜索 | ✅ 已实现 | `search()` ThreadPoolExecutor |
| AGEGraphStore | ✅ 已实现 | `src/powermem/storage/age/age_graph.py` |
| AGEGraphConfig | ✅ 已实现 | `src/powermem/storage/config/age.py` |
| 工厂注册 | ✅ 已实现 | `src/powermem/storage/factory.py` |
| SAG MCP 集成 | ⏳ 待实现 | — |

## 7. odoo-ai 项目精华吸收分析

**项目位置**：`D:\odoochain\odoo-ai`

### 7.1 odoo-ai 是什么

odoo-ai 是一个面向 Odoo 开发的 AI 技能框架，核心能力包括：
- **Spec-Driven Development (SDD)** — 13 阶段规范驱动开发流程
- **engram-drive** — 基于 Google Drive 的团队记忆同步
- **skill-evolver** — 自动检测开发模式并生成新技能
- **Hooks 层** — 15 个 Claude Code 钩子，覆盖会话全生命周期

### 7.2 可吸收的精华

| 能力 | odoo-ai 实现 | PowerMem 可吸收方式 |
|------|-------------|-------------------|
| **SDD 工作流** | explore→propose→spec→design→tasks→apply→verify→archive | 作为 PowerMem 的 Skill 层，将开发流程规范化 |
| **团队记忆同步** | engram-drive：每人写自己的 Google Drive 子目录，只读导入他人 | PowerMem 的 multi-agent 隔离 + 共享机制可参考此模式 |
| **skill-evolver** | 自动检测重复模式 → 分类 → 生成最小 diff → 确认应用 | PowerMem 的 SkillStore 可吸收此模式实现自我进化 |
| **Hooks 全生命周期** | SessionStart(5) → UserPromptSubmit(2) → PreToolUse(3) → PostToolUse(3) → PostCompact(3) → Stop(1) | PowerMem 的 Claude Code 插件可参考此钩子覆盖度 |
| **Phase→Adapter Routing** | 不同 SDD 阶段路由到不同 AI 模型 | PowerMem 的 LLM 配置可支持按任务类型选择模型 |
| **CodeGraph 集成** | AST 搜索替代 grep，减少 57% tokens | PowerMem 已有 CodeGraph 支持，可深化集成 |
| **6 层架构验证** | 数据层→安全→视图→控制器→前端→测试，逐层强制 | PowerMem 的记忆分类可参考此分层模型 |

### 7.3 具体吸收建议

#### 优先级 1：skill-evolver 模式吸收

odoo-ai 的 `skill-evolver` 是一个自我进化机制：检测重复模式 → 检查是否已存在 → 分类到合适的技能 → 生成最小变更 → 用户确认 → 应用并记录。

PowerMem 的 `SkillStore` 已经有技能存储能力，可以吸收此模式：

```python
# 概念性伪代码
class SkillEvolver:
    def detect_pattern(self, session_history: List[Dict]) -> Optional[Pattern]:
        """从会话历史中检测重复模式"""
        
    def check_duplicate(self, pattern: Pattern) -> bool:
        """检查是否已有类似技能"""
        
    def classify_domain(self, pattern: Pattern) -> str:
        """分类到合适的技能域"""
        
    def generate_diff(self, pattern: Pattern, target_skill: str) -> Diff:
        """生成最小变更"""
        
    def apply_with_confirmation(self, diff: Diff) -> bool:
        """用户确认后应用"""
```

#### 优先级 2：团队记忆同步模式

engram-drive 的核心设计：每人只写自己的目录，只读导入他人。零冲突、零服务器。

PowerMem 的 multi-agent 隔离已经有 `user_id`/`agent_id`/`run_id` 过滤，可以在此基础上实现类似的团队同步：

```
PowerMem team sync:
├── Alice/  ← Alice 的记忆（只有她写）
├── Bob/    ← Bob 的记忆（只有他写）
└── Carol/  ← Carol 的记忆（只有她写）
```

#### 优先级 3：SDD 工作流作为 PowerMem Skill

odoo-ai 的 13 阶段 SDD 流程可以封装为 PowerMem 的技能层，让记忆驱动的开发流程规范化：

```
/sdd-explore  → PowerMem 搜索相关记忆
/sdd-propose  → 基于记忆生成提案
/sdd-spec     → 规范化需求
/sdd-design   → 架构设计
/sdd-tasks    → 任务分解
/sdd-apply    → 实现（带记忆上下文）
/sdd-verify   → 验证（带历史模式）
/sdd-archive  → 归档到 PowerMem 记忆
```

### 7.4 不适合吸收的部分

| 能力 | 原因 |
|------|------|
| Odoo 专属知识库 | PowerMem 是通用记忆引擎，不需要领域特定知识 |
| Google Drive 同步 | PowerMem 有自己的存储后端（OceanBase/pgvector/SQLite） |
| PowerShell 钩子脚本 | PowerMem 用 Python，钩子实现方式不同 |
| Iris MCP 编排器 | PowerMem 自己就是 MCP server，不需要外部编排器 |
