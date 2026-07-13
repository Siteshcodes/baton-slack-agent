# Baton

# Baton

> 🏆 Slack Agent Builder Challenge 2026
>
> AI-powered institutional memory for volunteer-run organizations.
>
> **Ask questions. Get cited answers. Generate handover packs.**

**Institutional Memory Agent for Volunteer-Run Organizations**

> Every answer backed by receipts. Every handover done right.

Built for the **Slack Agent Builder Challenge 2026** (Slack Agent for Good Track).

---

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Slack Bolt](https://img.shields.io/badge/Slack-Bolt-4A154B)
![Groq](https://img.shields.io/badge/Groq-Llama3.3-green)
![Railway](https://img.shields.io/badge/Deploy-Railway-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Overview

Volunteer organizations lose valuable institutional knowledge whenever committee members or volunteers leave.

Baton transforms Slack into an organizational memory by combining:

- Slack Real-Time Search API
- Slack AI Agent
- Groq Llama 3.3 70B

Every answer is backed by direct links to the original Slack messages, making responses transparent and verifiable.

---

## Features

- Receipt-backed answers with source links
- AI-powered workspace search
- Automatic handover pack generation
- Slack-native Assistant experience
- Permission-aware search using Slack RTS API
- Honest responses when information is unavailable

---

##  System Architecture

```text
                                    ┌─────────────────────────┐
                                    │      Slack User         │
                                    └────────────┬────────────┘
                                                 │
                                                 ▼
                                    ┌─────────────────────────┐
                                    │  Slack Assistant Panel  │
                                    └────────────┬────────────┘
                                                 │
                                        Socket Mode Events
                                                 │
                                                 ▼
                        ┌────────────────────────────────────────────┐
                        │            Slack Bolt App                  │
                        │                app.py                      │
                        └────────────────┬───────────────────────────┘
                                         │
                                         ▼
                        ┌────────────────────────────────────────────┐
                        │       Assistant Middleware                 │
                        │             handlers.py                    │
                        └────────────────┬───────────────────────────┘
                                         │
                                         ▼
                        ┌────────────────────────────────────────────┐
                        │            Baton AI Engine                 │
                        │                                            │
                        │  • Context Management                      │
                        │  • Tool Calling                            │
                        │  • Retry Logic                             │
                        │  • Handover Generation                     │
                        └───────────────┬────────────────────────────┘
                                        │
                                Tool Invocation
                                         │
                    ┌────────────────────┴────────────────────┐
                    │                                         │
                    ▼                                         ▼
      ┌────────────────────────────┐          ┌────────────────────────────┐
      │  Slack RTS Search API      │          │      Groq Llama 3.3        │
      │                            │          │                            │
      │ • Workspace Search         │          │ • Reasoning                │
      │ • Permission Aware         │          │ • Tool Selection           │
      │ • Message Retrieval        │          │ • Response Generation      │
      └──────────────┬─────────────┘          └──────────────┬─────────────┘
                     │                                       │
                     └──────────────────┬────────────────────┘
                                        ▼
                        ┌────────────────────────────────────────────┐
                        │    Citation & Answer Composer              │
                        │                                            │
                        │ • Source Attribution                       │
                        │ • Markdown Formatting                      │
                        │ • Confidence Handling                      │
                        └───────────────┬────────────────────────────┘
                                        │
                      ┌─────────────────┴──────────────────┐
                      ▼                                    ▼
       ┌──────────────────────────┐        ┌──────────────────────────┐
       │  Slack Assistant Reply   │        │   Slack Canvas API       │
       │                          │        │                          │
       │ • Answer                 │        │ • Handover Document      │
       │ • Citations              │        │ • Knowledge Pack         │
       └──────────────────────────┘        └──────────────────────────┘
```
<img width="1024" height="1024" alt="architecture_diagram" src="https://github.com/user-attachments/assets/f1a1d1a7-a219-48af-a310-4f3813297565" />

## Tech Stack

| Component | Technology |
|----------|------------|
| Language | Python 3.11 |
| Framework | Slack Bolt |
| AI Model | Groq Llama 3.3 70B |
| Search | Slack Real-Time Search API |
| UI | Slack Assistant |
| Deployment | Railway / Docker |

---

## Getting Started

Clone the repository.

```bash
git clone https://github.com/Siteshcodes/baton-slack-agent.git
cd baton-slack-agent
```

Create a virtual environment.

```bash
python -m venv .venv
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Configure environment variables.

```bash
cp .env.example .env
```

Run the application.

```bash
python app.py
```
## Live Deployment

Health Endpoint

https://your-app.up.railway.app/

Status

{
  "status":"ok",
  "service":"Baton"
}
---

## Example Questions

```
How do we book the community centre?

Who is our arbiter contact?

When is the insurance renewal?

Generate handover pack for @username
```

---

## Repository Structure
---
.
├── app.py
├── agent.py
├── handlers.py
├── manifest.json
├── requirements.txt
├── README.md
├── ARCHITECTURE.md
├── DEPLOY.md
├── TESTING.md
└── .env.example

---

## Project Impact

Baton helps volunteer organizations:

- Preserve institutional knowledge
- Reduce onboarding time
- Generate structured handover documents
- Increase transparency through cited answers

---

## Documentation

- Architecture — `ARCHITECTURE.md`
- Deployment — `DEPLOY.md`
- Testing — `TESTING.md`

---

## License

MIT License
