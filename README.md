# Deal Desk

> AI-powered multi-agent deal desk built on [Band](https://www.band.ai/) for the
> Band of Agents Hackathon (Track 1 — Internal Enterprise Workflows).

## What it does

Drop a customer RFP into a Band chat room. A **Coordinator** agent reads it and
recruits the right specialist agents into the room at runtime. Each specialist
drafts their section. A **Reviewer** agent red-teams every section and pushes
weak work back for revision. If a discount exceeds 20%, a human is pulled in
to approve.

## Agents

| Agent | Model | Role |
|-------|-------|------|
| Coordinator | GPT-4o | Reads RFP, recruits specialists, routes review, finalizes |
| Pricing Specialist | GPT-4o | Itemized pricing proposal |
| Technical Specialist | GPT-4o | Technical solution mapped to requirements |
| Reviewer | GPT-4o | Adversarial red-team across all sections |

## Quick Start

```bash
uv add "band-sdk[langgraph]" langchain-openai python-dotenv pyyaml
cp .env.example .env                             # add your keys
cp agent_config.example.yaml agent_config.yaml  # add agent UUIDs + keys

# each in its own terminal:
uv run python agents/coordinator.py
uv run python agents/specialist.py pricing_agent
uv run python agents/specialist.py technical_agent
uv run python agents/reviewer.py
```

Then create a Band room, add all 4 agents, and send:
`@Coordinator Please handle this RFP: ...`

## Built With
Band SDK · LangGraph · GPT-4o via AI/ML API · Python 3.12