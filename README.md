# Deal Desk 🤝

> AI-powered Multi-Agent Deal Desk built on **Band** for the **Band of Agents Hackathon (Track 1 – Internal Enterprise Workflows)**.
>
> Deal Desk transforms customer RFPs into vetted, ready-to-send enterprise proposals through dynamic agent recruitment, adversarial review, and human-in-the-loop approvals.

---

## 🚀 Demo

### Live Demo

**Streamlit App:**
https://deal-desk-aim-nexus.streamlit.app/

## Demo Video 

Watch the demo here :
[ Demo Video ](https://drive.google.com/file/d/1RVQwgcvrxsLRm7oe2oxYmchXrwiBAGhd/view?usp=sharing)

## Problem

Enterprise proposal creation is slow, fragmented, and difficult to scale.

A typical proposal often requires coordination between:

* Sales
* Pricing
* Technical Solution Architects
* Legal Teams
* Management Approvers

This process involves multiple handoffs, repeated reviews, inconsistent quality, and delays in customer response times.

---

## Solution

Deal Desk creates an AI proposal team on demand.

Instead of relying on a single AI agent, a Coordinator dynamically recruits only the specialists required for a given RFP.

A simple renewal request may require only Pricing.

A highly regulated enterprise migration may require:

* Pricing
* Technical
* Legal
* Reviewer

The team assembles itself based on the actual requirements of the deal.

---

## Why Band?

Band is not a wrapper around the workflow.

Band is the workflow.

Without Band, the system cannot function.

Deal Desk relies on Band for:

### Dynamic Agent Discovery

The Coordinator discovers and recruits specialists at runtime.

### Multi-Agent Coordination

All delegation, routing, handoffs, and collaboration occur through Band messaging.

### Human-in-the-Loop Approvals

Humans participate directly inside the same workspace as agents.

### Review Loops

Agents collaborate, revise, and challenge each other's work through Band conversations.

Band serves as the orchestration layer for the entire proposal generation process.

---

## How It Works

```text
Customer RFP
      ↓
Coordinator
      ↓
Dynamic Recruitment
      ↓
 ┌─────────────┐
 │ Pricing     │
 │ Technical   │
 │ Legal       │
 └─────────────┘
      ↓
Reviewer
      ↓
Human Approval
 (if required)
      ↓
Final Proposal
```

---

## Agent Team

| Agent                | Responsibility                                                                                   |
| -------------------- | ------------------------------------------------------------------------------------------------ |
| Coordinator          | Reads RFP, recruits specialists, routes tasks, enforces business rules, assembles final proposal |
| Pricing Specialist   | Generates pricing recommendations and budget-aware proposals                                     |
| Technical Specialist | Maps technical requirements to implementation plans                                              |
| Legal Specialist     | Reviews compliance, contracts, SLAs, and regulatory requirements                                 |
| Reviewer             | Performs adversarial quality review and requests revisions                                       |

---

## Human-in-the-Loop Rules

Deal Desk includes mandatory human approval for high-risk scenarios.

### Escalation Trigger 1

```text
Discount > 20%
```

The workflow pauses and requests approval.

### Escalation Trigger 2

```text
Total Cost > Customer Budget
```

The proposal is sent back for revision before proceeding.

This ensures business oversight while maintaining automation.

---

## Streamlit Demo Experience

For hackathon judging and public demonstration, Deal Desk includes a Streamlit-based interface that visualizes the same workflow used inside Band.

Features:

* Customer RFP Intake
* Dynamic Agent Recruitment
* Live Agent Workflow
* Activity Feed
* Proposal Generation
* Executive Summary
* Risk Analysis
* Human Approval Simulation

The demo allows judges to observe the complete proposal generation lifecycle in real time.

---

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Environment

```bash
cp .env.example .env
cp agent_config.example.yaml agent_config.yaml
```

Add:

* AI/ML API Key
* Agent UUIDs
* Band configuration

### 3. Verify Setup

```bash
uv run python verify_setup.py
```

Expected output:

```text
Connected as: Coordinator
```

---

## Run Agents

Start each agent in a separate terminal.

### Coordinator

```bash
uv run python agents/coordinator.py
```

### Pricing

```bash
uv run python agents/specialist.py pricing_agent
```

### Technical

```bash
uv run python agents/specialist.py technical_agent
```

### Legal

```bash
uv run python agents/specialist.py legal_agent
```

### Reviewer

```bash
uv run python agents/reviewer.py
```

---

## Using Deal Desk Inside Band

Create a Band room containing:

* Coordinator
* Reviewer
* Human Participant

Do not manually add specialist agents.

The Coordinator recruits them automatically.

Example:

```text
@Coordinator Please handle this RFP:

We require migration from Salesforce to HubSpot
for 2500 employees across US and EU regions with
GDPR compliance requirements.
```

The Coordinator will dynamically assemble the required team and begin processing.

---

## Run the Streamlit Demo

```bash
uv run streamlit run streamlit_app.py
```

You can provide the API key via:

* `.env`
* Streamlit Secrets
* Sidebar Configuration

---

## Project Structure

```text
deal-desk/
├── agents/
│   ├── coordinator.py
│   ├── specialist.py
│   └── reviewer.py
│
├── frontend/
│   └── orchestrator.py
│
├── prompts.py
├── verify_setup.py
├── streamlit_app.py
├── sample_rfp.md
├── sample_rfp_escalation.md
├── requirements.txt
├── .env.example
└── agent_config.example.yaml
```

---

## Example Scenarios

### Scenario 1

Simple License Renewal

Agents Recruited:

* Pricing

### Scenario 2

Enterprise CRM Migration

Agents Recruited:

* Pricing
* Technical
* Reviewer

### Scenario 3

Regulated Enterprise Deployment

Agents Recruited:

* Pricing
* Technical
* Legal
* Reviewer

---

## Tech Stack

* Band SDK
* LangGraph
* GPT-4o (AI/ML API)
* Streamlit
* Python 3.12

---

## Key Features

✅ Dynamic Agent Recruitment

✅ Multi-Agent Collaboration

✅ Adversarial Review Loops

✅ Human-in-the-Loop Governance

✅ Budget-Aware Proposal Generation

✅ Risk Identification

✅ Enterprise Workflow Automation

---

## Team

**Aim Nexus**

Band of Agents Hackathon 2026

Building practical multi-agent systems for enterprise workflows.
