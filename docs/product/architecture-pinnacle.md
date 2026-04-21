# Technical Architecture Document: GADK Pinnacle (v2.0)

**Version:** 1.0  
**Date:** 2026-04-20  
**Status:** Target State Architecture  
**Classification:** Design Document

---

## 1. Executive Summary

This document describes the target-state architecture for GADK v2.0 — the pinnacle vision of a fully autonomous cognitive foundry. It builds upon the current v0.1.0 foundation while introducing advanced capabilities for typed agents, graph-based workflows, semantic retrieval, multi-repository operations, and continuous self-improvement.

**Core Principle:** Google ADK remains the sole control plane. All integrations (PydanticAI, LangGraph, LlamaIndex) are supporting layers that enhance ADK rather than replace it.

---

## 2. Current State Architecture (v0.1.0)

### 2.1 Current Components

```
┌─────────────────────────────────────────────────────────────┐
│                    GOOGLE ADK CONTROL PLANE                   │
├─────────────────────────────────────────────────────────────┤
│  Orchestrator → Ideator → Architect → Builder → Critic      │
│       ↓          ↓          ↓          ↓          ↓       │
│   Governor ← Pulse/FinOps                                    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      SERVICES LAYER                          │
│  ├─ PhaseController (SDLC phase management)                   │
│  ├─ QualityGates (pluggable validation)                    │
│  ├─ StateManager (persistence)                             │
│  ├─ SelfPrompt (gap analysis)                                │
│  └─ RetrievalContext (knowledge)                           │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                       TOOLS LAYER                          │
│  ├─ GitHubTool (repository operations)                     │
│  ├─ Filesystem (local operations)                          │
│  ├─ SandboxExecutor (code execution)                       │
│  └─ SmitheryBridge (marketplace)                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Current Data Stores
- **state.json** — Atomic JSON task state
- **events.jsonl** — Append-only event log
- **sessions.db** — SQLite session data
- **prompt_queue.jsonl** — Pending prompts

### 2.3 Current Limitations
1. Agent handoffs rely on prompt text and free-form strings
2. No persistent agent memory across sessions
3. Review/rework cycles are ad hoc loops
4. Retrieval is keyword-based only
5. Single-repository focus
6. No learning from past outcomes

---

## 3. Target State Architecture (v2.0)

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Web UI   │  │ CLI      │  │ Slack    │  │ IDE      │  │ Mobile      │  │
│  │ Dashboard│  │ Enhanced │  │ Bot      │  │ Plugins  │  │ Companion   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬──────┘  │
└───────┼─────────────┼─────────────┼─────────────┼──────────────┼─────────┘
        │             │             │             │              │
        └─────────────┴─────────────┴─────────────┴──────────────┘
                                   │
┌──────────────────────────────────┴──────────────────────────────────────┐
│                         API GATEWAY LAYER                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  REST API │ GraphQL │ Webhooks │ MCP Server │ SDK (Python/TS/Go)  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┴──────────────────────────────────────┐
│                      GOOGLE ADK CONTROL PLANE                         │
│                          (SINGLE SOURCE OF TRUTH)                     │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    ORCHESTRATION ENGINE                         │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────────────┐ │  │
│  │  │ Router  │  │ Planner │  │ Monitor │  │ Recovery Manager  │ │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └─────────┬─────────┘ │  │
│  └───────┼────────────┼────────────┼──────────────────┼───────────┘  │
└──────────┼────────────┼────────────┼──────────────────┼──────────────┘
           │            │            │                  │
┌──────────┴────────────┴────────────┴──────────────────┴──────────────┐
│                     AGENT ECOSYSTEM (v2.0)                           │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Ideator  │  │ Architect│  │ Builder  │  │ Critic   │           │
│  │ (PLAN)   │  │(ARCHITECT)│  │(IMPLEMENT)│  │ (REVIEW) │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘           │
│       │             │             │             │                    │
│  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  ┌─┴──────────┐         │
│  │ Governor │  │ Pulse    │  │ FinOps   │  │ Specialists│         │
│  │ (GOVERN) │  │(OPERATE) │  │(OPERATE) │  │ (Dynamic)  │         │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘         │
│                                                                      │
│  Agent Capabilities:                                                 │
│  • Typed decisions (PydanticAI)                                       │
│  • Persistent memory (Vector store)                                  │
│  • Multi-model routing (LiteLLM)                                    │
│  • Self-improvement (Meta-learning)                                  │
└──────────────────────────────────────────────────────────────────────┘
           │            │            │             │
┌──────────┴────────────┴────────────┴─────────────┴──────────────────┐
│                    WORKFLOW ORCHESTRATION                          │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              LANGGRAPH WORKFLOW ENGINE                       │  │
│  │                                                              │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │  │
│  │  │ State Machine│───▶│   Branch    │───▶│   Parallel  │    │  │
│  │  └─────────────┘    └─────────────┘    └─────────────┘    │  │
│  │         │                  │                  │            │  │
│  │         ▼                  ▼                  ▼            │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │  │
│  │  │  Bounded    │    │  Conditional │    │  Recovery   │    │  │
│  │  │  Retries    │    │   Logic     │    │   Paths     │    │  │
│  │  └─────────────┘    └─────────────┘    └─────────────┘    │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
           │            │            │             │
┌──────────┴────────────┴────────────┴─────────────┴──────────────────┐
│                      SERVICES LAYER (Enhanced)                     │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │ PhaseController  │  │  Quality Gates   │  │  State Manager   │ │
│  │ (v2)             │  │  (Enhanced)      │  │  (Distributed)   │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │ SelfPrompt       │  │  Knowledge Graph │  │  Fleet Manager   │ │
│  │ (AI-Powered)     │  │  (Neo4j/Custom)  │  │  (Multi-Repo)    │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │ Cost Tracker     │  │  Policy Engine   │  │  Analytics       │ │
│  │ (Real-time)      │  │  (RBAC)          │  │  (Aggregated)    │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
           │            │            │             │
┌──────────┴────────────┴────────────┴─────────────┴──────────────────┐
│                    KNOWLEDGE & RETRIEVAL                           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                 LLAMAINDEX RETRIEVAL STACK                   │ │
│  │                                                              │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐           │ │
│  │  │  Vector    │  │   Graph    │  │  Hybrid     │           │ │
│  │  │  Search    │  │   RAG      │  │  Search     │           │ │
│  │  │(Pinecone/  │  │(Neo4j/     │  │(Multi-modal)│           │ │
│  │  │ Weaviate)  │  │ Memgraph)  │  │             │           │ │
│  │  └────────────┘  └────────────┘  └────────────┘           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Data Sources:                                                      │
│  • Code repositories (semantic indexing)                            │
│  • Documentation (confluence, notion, markdown)                     │
│  • External APIs (Stack Overflow, API docs)                         │
│  • Communication (Slack, email threads)                              │
└─────────────────────────────────────────────────────────────────────┘
           │            │            │             │
┌──────────┴────────────┴────────────┴─────────────┴──────────────────┐
│                        EXECUTION LAYER                             │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │ GitHub Tool │  │ Sandbox     │  │ Smithery    │  │ Custom    │ │
│  │ (Enhanced)  │  │ Executor    │  │ Bridge      │  │ MCP Tools │ │
│  │             │  │ (Isolated)  │  │ (v2)        │  │           │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA PERSISTENCE v2.0                          │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐
│  PostgreSQL  │  │    Redis     │  │ Vector DB    │  │   Object   │
│  (Primary)   │  │   (Cache)    │  │ (Pinecone/   │  │  Storage    │
│              │  │              │  │  Weaviate)   │  │  (S3/GCS)   │
├──────────────┤  ├──────────────┤  ├──────────────┤  ├────────────┤
│ • Work Items │  │ • Sessions   │  │ • Code       │  │ • Artifacts │
│ • Agents     │  │ • Rate       │  │   Embeddings │  │ • Logs      │
│ • Workflows  │  │   Limiting   │  │ • Doc        │  │ • Checkpoints│
│ • Events     │  │ • Job Queues │  │   Embeddings │  │ • Backups   │
│ • Audit Log  │  │ • Pub/Sub    │  │ • Knowledge  │  │             │
└──────────────┘  └──────────────┘  │   Graph      │  └────────────┘
                                    └──────────────┘

Migration Path:
• Phase 1: JSON/SQLite → PostgreSQL
• Phase 2: Add Redis caching layer
• Phase 3: Add vector DB for RAG
• Phase 4: Add object storage for artifacts
```

---

## 4. Component Specifications

### 4.1 Enhanced Agent System

#### Agent Contract (PydanticAI)
```python
from pydantic import BaseModel
from enum import Enum

class AgentDecision(BaseModel):
    """Structured decision output for all agents."""
    confidence: float  # 0.0-1.0
    reasoning: str
    action: ActionType
    payload: dict
    estimated_cost_usd: float
    estimated_duration_seconds: int
    required_approvals: list[str]
    
class AgentMemory(BaseModel):
    """Persistent agent memory entry."""
    agent_id: str
    memory_type: str  # "context", "learning", "preference"
    content: dict
    embedding: list[float]
    timestamp: datetime
    ttl: datetime | None
```

#### Agent Types

| Agent | Input | Output | Memory |
|-------|-------|--------|--------|
| Ideator | User goals, trends | Task proposals | Past proposals, success rates |
| Architect | Task, codebase | ADR, implementation plan | Design patterns, tech choices |
| Builder | ADR, requirements | Code, tests | Coding style, common patterns |
| Critic | Code, ADR | Review verdict | Review history, common issues |
| Governor | Review evidence | Release decision | Policy knowledge, past decisions |
| Pulse | Metrics, alerts | Health status, actions | System baseline, anomalies |
| FinOps | Costs, usage | Optimization recommendations | Cost patterns, budgets |

### 4.2 LangGraph Workflow Engine

```python
from langgraph.graph import StateGraph
from typing import TypedDict

class WorkflowState(TypedDict):
    work_item_id: str
    phase: Phase
    attempts: int
    evidence: dict
    approved: bool | None

# Review-Rework Cycle Graph
def build_review_graph():
    graph = StateGraph(WorkflowState)
    
    graph.add_node("review", critic_review)
    graph.add_node("evaluate", evaluate_verdict)
    graph.add_node("rework", builder_rework)
    graph.add_node("approve", governor_approve)
    
    graph.add_edge("review", "evaluate")
    graph.add_conditional_edges(
        "evaluate",
        should_rework,
        {True: "rework", False: "approve"}
    )
    graph.add_edge("rework", "review")  # Loop back
    
    return graph.compile()
```

### 4.3 Retrieval System (LlamaIndex)

```python
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.pinecone import PineconeVectorStore

class KnowledgeSystem:
    """Unified knowledge retrieval system."""
    
    def __init__(self):
        self.code_index: VectorStoreIndex  # Semantic code search
        self.doc_index: VectorStoreIndex   # Documentation
        self.conversation_index: VectorStoreIndex  # Past conversations
        self.knowledge_graph: GraphStore  # Entity relationships
    
    async def query(
        self,
        query: str,
        context: QueryContext,
        top_k: int = 5
    ) -> RetrievedContext:
        """Hybrid retrieval across all sources."""
        # Vector search for semantic match
        # Graph traversal for relationships
        # Ranking by relevance and recency
        pass
```

### 4.4 Fleet Manager (Multi-Repository)

```python
class FleetManager:
    """Manage repository fleet operations."""
    
    async def register_repository(self, repo: RepositoryConfig) -> RepoHandle
    async def bulk_operation(
        self,
        selector: RepoSelector,
        operation: Operation,
        strategy: ExecutionStrategy = Parallel()
    ) -> BulkResult
    async def dependency_graph(self) -> DependencyGraph
    async def impact_analysis(self, change: Change) -> ImpactReport
    async def mass_update(
        self,
        update: UpdateSpec,
        rollout: RolloutStrategy = Canary()
    ) -> RolloutStatus
```

### 4.5 Self-Improvement Engine

```python
class SelfImprovementEngine:
    """Continuous system optimization."""
    
    async def analyze_gaps(self) -> list[Gap]:
        """Identify improvement opportunities."""
        # Coverage gaps
        # Performance bottlenecks
        # Pattern recognition
        pass
    
    async def optimize_prompts(self) -> list[PromptOptimization]:
        """A/B test and improve prompts."""
        # Track prompt effectiveness
        # Generate variants
        # Measure outcomes
        pass
    
    async def suggest_tools(self) -> list[ToolSuggestion]:
        """Recommend new tools based on usage patterns."""
        # Analyze task patterns
        # Identify automation opportunities
        # Generate tool specifications
        pass
```

---

## 5. Integration Architecture

### 5.1 External Integrations

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL INTEGRATIONS                       │
└─────────────────────────────────────────────────────────────────┘

LLM Providers:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  OpenRouter │  │   OpenAI    │  │  Anthropic  │  │    Google   │
│  (Primary)  │  │  (Direct)   │  │  (Direct)   │  │   (Direct)  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       └─────────────────┴─────────────────┴─────────────────┘
                           │
                    ┌──────┴──────┐
                    │   LiteLLM   │
                    │   Router    │
                    └──────┬──────┘
                           │
Code Repository:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   GitHub    │  │   GitLab    │  │   Bitbucket │
│  (Primary)  │  │  (Planned)  │  │  (Planned)  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       └─────────────────┴─────────────────┘
                           │
                    ┌──────┴──────┐
                    │  VCS Abstraction │
                    └─────────────┘

Communication:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│    Slack    │  │   Discord   │  │    Email    │
│  (Primary)  │  │  (Planned)  │  │  (Planned)  │
└─────────────┘  └─────────────┘  └─────────────┘

IDE:
┌─────────────┐  ┌─────────────┐
│  VS Code    │  │  JetBrains  │
│  (Planned)  │  │  (Planned)  │
└─────────────┘  └─────────────┘

Observability:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Datadog    │  │  New Relic  │  │   Grafana   │
│  (Optional) │  │  (Optional) │  │  (Built-in) │
└─────────────┘  └─────────────┘  └─────────────┘
```

### 5.2 MCP (Model Context Protocol)

```python
# MCP Server for external tool integration
from mcp.server import Server

app = Server("gadk-server")

@app.tool()
async def swarm_status() -> Status:
    """Get current swarm health and status."""
    pass

@app.tool()
async def queue_prompt(prompt: str) -> TaskId:
    """Add a new prompt to the queue."""
    pass

@app.tool()
async def get_work_item(id: str) -> WorkItem:
    """Retrieve work item details."""
    pass
```

---

## 6. Security Architecture

### 6.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                        SECURITY ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────────┘

Layer 5: Application
├─ Input validation (Pydantic schemas)
├─ Output sanitization
├─ Rate limiting per user/agent
└─ Audit logging (all actions)

Layer 4: API
├─ Authentication (OAuth 2.0 / API keys)
├─ Authorization (RBAC)
├─ TLS 1.3 (in transit)
└─ CORS policies

Layer 3: Service
├─ Service-to-service auth (mTLS)
├─ Secrets management (Vault)
├─ Sandboxed execution
└─ Circuit breakers

Layer 2: Data
├─ Encryption at rest (AES-256)
├─ Field-level encryption for PII
├─ Backup encryption
└─ Key rotation

Layer 1: Infrastructure
├─ Network segmentation
├─ WAF rules
├─ DDoS protection
└─ Vulnerability scanning
```

### 6.2 Agent Sandbox

```python
class Sandbox:
    """Isolated execution environment for agent code."""
    
    def __init__(self):
        self.network_policy = NetworkPolicy(
            allowlist=["github.com", "pypi.org"],
            deny_inbound=True
        )
        self.resource_limits = ResourceLimits(
            cpu="1 core",
            memory="1GB",
            disk="10GB",
            timeout="5 minutes"
        )
        self.capabilities = CapabilitySet(
            file_write=False,  # Read-only filesystem
            network=True,      # But restricted
            subprocess=False   # No shell access
        )
```

---

## 7. Deployment Architecture

### 7.1 Kubernetes Deployment

```yaml
# Simplified deployment structure
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gadk-orchestrator
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: orchestrator
          image: gadk/orchestrator:v2.0
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "2000m"
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: gadk-workers
spec:
  serviceName: workers
  replicas: 5
  template:
    spec:
      containers:
        - name: worker
          image: gadk/worker:v2.0
```

### 7.2 Scaling Strategy

| Component | Min | Max | Scaling Trigger |
|-----------|-----|-----|-----------------|
| Orchestrator | 2 | 10 | CPU > 70% |
| Workers | 3 | 50 | Queue depth > 100 |
| Vector DB | 2 | 10 | Query latency > 100ms |
| Cache | 2 | 6 | Hit rate < 80% |

---

## 8. Migration Strategy

### Phase 1: Foundation (Months 1-3)
- Migrate JSON state → PostgreSQL
- Add Redis caching layer
- Implement PydanticAI integration
- Deploy LangGraph for workflows

### Phase 2: Intelligence (Months 4-6)
- Add vector search with Pinecone/Weaviate
- Implement agent memory system
- Deploy knowledge graph
- Add self-improvement engine

### Phase 3: Scale (Months 7-9)
- Multi-repository fleet manager
- Advanced dashboard
- IDE integrations
- Mobile companion app

### Phase 4: Ecosystem (Months 10-12)
- Agent marketplace
- Third-party integrations
- Community features
- Enterprise features

---

## 9. Monitoring & Observability

### 9.1 Metrics

```python
# Key metrics collected
AGENT_DECISION_LATENCY = Histogram("agent_decision_seconds")
WORKFLOW_DURATION = Histogram("workflow_duration_seconds")
WORKFLOW_SUCCESS_RATE = Gauge("workflow_success_rate")
LLM_TOKEN_USAGE = Counter("llm_tokens_total")
LLM_COST_USD = Counter("llm_cost_usd_total")
RETRIEVAL_LATENCY = Histogram("retrieval_latency_seconds")
GATE_FAILURES = Counter("gate_failures_total")
AGENT_MEMORY_HITS = Counter("agent_memory_hits_total")
```

### 9.2 Alerting

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Error Rate | >5% errors in 5min | Critical |
| LLM Cost Spike | >2x baseline | Warning |
| Workflow Stuck | >1hr no progress | Warning |
| Agent Memory Miss | >80% miss rate | Info |
| Disk Full | >85% usage | Critical |

---

## 10. Appendix

### A. Technology Stack

| Layer | Technology | Alternative |
|-------|------------|-------------|
| Control Plane | Google ADK | - |
| Workflow | LangGraph | Temporal, Cadence |
| LLM Routing | LiteLLM | - |
| Agent Framework | PydanticAI | LangChain Agents |
| Retrieval | LlamaIndex | Direct Vector DB |
| Vector DB | Pinecone | Weaviate, Milvus |
| Database | PostgreSQL | MySQL, CockroachDB |
| Cache | Redis | Memcached |
| Queue | Redis/RabbitMQ | Kafka |
| Storage | S3/GCS | MinIO |
| API | FastAPI | Django REST |
| Frontend | React/Vue | Svelte |
| Mobile | React Native | Flutter |

### B. API Versioning

- Current: v1 (stable)
- Next: v2 (in development)
- Deprecation: 6 months notice
- Breaking changes: major version bump

### C. References

- Vision Document: `product-vision.md`
- Requirements: `product-requirements.md`
- Roadmap: `roadmap.md`
- Current Specs: `docs/superpowers/specs/`
