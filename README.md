# ReviewPilot – AI Powered Code Review Platform
 
## Overview

ReviewPilot is an AI-powered code review platform that automates Pull Request (PR) analysis for GitHub repositories. The system leverages Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), and GitHub integration to identify bugs, security vulnerabilities, code quality issues, and architectural violations before code is merged.

---

# Problem Statement

Software teams rely on manual Pull Request reviews to ensure code quality and security. However:

* Manual reviews are time-consuming.
* Reviewers may overlook bugs and vulnerabilities.
* Large teams experience review bottlenecks.
* Coding standards are not always consistently enforced.

The goal is to automate the first level of code review using AI while integrating seamlessly into the GitHub development workflow.

---

# Proposed Solution

ReviewPilot connects with GitHub repositories and automatically reviews Pull Requests using Artificial Intelligence.

The system:

* Retrieves code changes from GitHub.
* Analyzes modified code using an LLM.
* Retrieves relevant coding standards through RAG.
* Calculates risk scores.
* Generates actionable review suggestions.
* Displays results through a centralized dashboard.

---

# AI Architecture

```text
┌───────────────────┐
│   GitHub PR       │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ GitHub API/Webhook│
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Pull Request Diff │
│ Extraction Engine │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ AI Review Engine  │
│ (Groq + LangChain)│
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ RAG Retrieval     │
│ Engine            │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Qdrant Vector DB  │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Coding Guidelines │
│ Best Practices    │
│ Security Rules    │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Risk Scoring      │
│ Engine            │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ PostgreSQL        │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Next.js Dashboard │
└───────────────────┘
```

---

# AI Concepts Used

## 1. Large Language Model (LLM)

Used for:

* Code analysis
* Bug detection
* Security review
* Design review
* Code improvement suggestions

Model Provider:

* Groq

---

## 2. Retrieval-Augmented Generation (RAG)

Used to provide project-specific knowledge to the LLM.

Retrieves:

* Coding standards
* Security guidelines
* Best practices
* Architectural rules

Benefits:

* Improves review accuracy
* Reduces hallucination
* Supports organization-specific policies

---

## 3. Embeddings

Text documents are converted into vector representations using Sentence Transformers.

Used for:

* Semantic similarity search
* Guideline retrieval

---

## 4. Vector Database

Qdrant stores vector embeddings of coding guidelines and best practices.

Responsibilities:

* Similarity search
* Fast retrieval
* Context enrichment

---

## 5. Risk Scoring

Review findings are categorized by severity:

* Critical
* High
* Medium
* Low

A cumulative risk score is generated to help developers prioritize fixes.

---

# Technology Stack

## Frontend

* Next.js
* React
* Tailwind CSS
* Recharts

## Backend

* FastAPI
* Python
* SQLAlchemy
* Alembic

## Database

* PostgreSQL

## AI & Machine Learning

* Groq LLM
* LangChain
* Sentence Transformers
* Qdrant

## Integration

* GitHub API
* GitHub Webhooks

## Security

* JWT Authentication

---

# Workflow

1. User connects GitHub repository.
2. Developer creates Pull Request.
3. GitHub triggers webhook/API event.
4. Code diffs are extracted.
5. AI Review Engine analyzes modified code.
6. RAG retrieves relevant coding standards.
7. Risk score is calculated.
8. Results are stored in PostgreSQL.
9. Dashboard displays findings.
10. Feedback is provided to developers.

---

# Key Features

* Automated AI Code Review
* GitHub Integration
* Pull Request Analysis
* Risk Assessment
* RAG-Based Context Retrieval
* Repository Management
* JWT Authentication
* Review Analytics Dashboard
* Review History Tracking

---

# Future Enhancements

* Multi-Language Support
* CI/CD Integration
* Team Performance Analytics
* Custom Organization Guidelines
* Security Compliance Auditing

---

# Team Members

* Kalpana G
* Rahul Vignesh Kumaran K
* Swetha J
* Subiksha M
