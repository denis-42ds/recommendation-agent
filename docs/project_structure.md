recommendation-agent/
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── docs/
│   ├── architecture/
│   │   ├── overview.md
│   │   └── data-flow.md
│   │
│   ├── decisions/
│   │   └── ADR-000-template.md
│   │
│   ├── requirements/
│   │   └── assumptions.md
│   │
│   ├── demo/
│   │   └── demo-script.md
│   │
│   └── economics/
│       └── cost-estimation.md
│
├── src/
│   └── recommendation_agent/
│       │
│       ├── api/
│       │   ├── routes/
│       │   └── schemas/
│       │
│       ├── agent/
│       │   ├── orchestrator.py
│       │   ├── state.py
│       │   └── tools/
│       │
│       ├── core/
│       │   ├── config.py
│       │   └── logging.py
│       │
│       ├── domain/
│       │   ├── models/
│       │   └── rules/
│       │
│       ├── recommenders/
│       │   ├── candidates.py
│       │   ├── ranking.py
│       │   └── strategies/
│       │
│       ├── services/
│       │   ├── customer.py
│       │   ├── catalog.py
│       │   └── recommendation.py
│       │
│       ├── infrastructure/
│       │   ├── repositories/
│       │   └── llm/
│       │
│       └── main.py
│
├── frontend/
│
├── data/
│   ├── samples/
│   └── .gitkeep
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── scripts/
│   └── context_pack.py
│
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── compose.yaml
├── LICENSE
├── Makefile
├── pyproject.toml
├── README.md
└── STATE.md
