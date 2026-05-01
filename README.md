# 💍 IMTool Improved
### Enterprise-Grade Jewellery Inventory & Sales Management System

`IMTool Improved` is a sophisticated Streamlit-based platform designed for high-value inventory management. It seamlessly blends robust CRUD operations with a state-of-the-art **Agentic AI Pipeline** for natural language business intelligence and policy retrieval.

---

## ✨ Key Features

- **🏆 Premium UI/UX**: Custom-designed Cinzel/Outfit aesthetic tailored for luxury retail.
- **🛡️ Secure Access**: Bcrypt-encrypted authentication with role-aware session gating.
- **📦 Full CRUD Lifecycle**: Manage Stocks, Sales, Bookings, Purchases, Customers, and Salesmen.
- **🤖 Agentic Intelligence**: A 4-agent RAG pipeline (Understanding -> SQL -> Eval -> Summary) that turns natural language questions into data-driven insights.
- **🗄️ ACID Compliance**: Atomic, Consistent, Isolated, Durable database transactions via PostgreSQL connection pooling.
- **📄 RAG Knowledge**: Built-in retrieval-augmented generation for store policies and operational manuals.

---

## 🛠️ Tech Stack

- **Frontend**: [Streamlit](https://streamlit.io/) with Premium Custom CSS.
- **Backend/Logic**: Python 3.11 with `psycopg2` for PostgreSQL interaction.
- **Intelligence**: [OpenAI GPT-4o-mini](https://openai.com/) (Agentic Framework).
- **Database**: PostgreSQL (with read-only security for AI queries).
- **Redaction**: Built-in PII redaction for safe LLM interaction.

---

## 📂 Project Architecture

```
├── app.py                  # Entry point & Navigation
├── auth_controller.py      # Security & Session Management
├── database_manager.py     # Connection Pooling & ACID Logic
├── agents/                 # 4-Agent AI Pipeline
│   ├── question_understanding.py
│   ├── sql_query_agent.py
│   ├── data_evaluation_agent.py
│   └── summary_agent.py
├── utils/                  # Core helpers (RAG, logging, etc.)
├── knowledge/              # RAG Source Material
├── config/                 # Query & Prompt Registries
└── docs/                   # Full System Documentation
```

> [!TIP]
> **Detailed Workflow Diagram**: For a deep dive into the function-level logic (Bootstrap, Auth, DB Layer, AI Pipeline), refer to my recently generated workflow diagrams.

---

## 🚀 Quick Start

### 1. Requirements
- **Python 3.11+**
- **PostgreSQL** instance with appropriate schema.
- **OpenAI API Key** (for Agentic features).

### 2. Configuration
Create a `.streamlit/secrets.toml` file with:
```toml
[connections.postgresql]
host = "..."
dbname = "..."
user = "..."
password = "..."
schema = "konghin"

[openai]
api_key = "..."
model = "gpt-4o-mini"
```

### 3. Execution
```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 🔍 System Audits & Guides

- **Security**: [SECURITY_REVIEW.md](file:///docs/reviews/SECURITY_REVIEW.md)
- **Performance**: [PERFORMANCE_REVIEW.md](file:///docs/reviews/PERFORMANCE_REVIEW.md)
- **Structure**: [STRUCTURE_GUIDE.md](file:///docs/guides/STRUCTURE_GUIDE.md)
- **Functions**: [PROJECT_DETAILED_DIAGRAM.md](file:///docs/PROJECT_DETAILED_DIAGRAM.md)

---
© 2025 Chop Kong Hin. All rights reserved.
