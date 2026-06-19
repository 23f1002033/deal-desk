# Deal Desk 🤝

> An AI **Deal Desk** built on [Band](https://www.band.ai/) for the Band of Agents
> Hackathon (Track 1 - Internal Enterprise Workflows). A team of specialized agents
> turns a customer RFP into a vetted, ready-to-send proposal - coordinating entirely
> through Band.

## The idea

Drop a customer RFP into a Band chat room and @mention the Coordinator. From there,
everything happens **inside Band**:

1. The **Coordinator** reads the RFP and **recruits only the specialists the RFP
   actually needs** - at runtime. A simple license renewal pulls in only Pricing.
   A contract-heavy, regulated deal pulls in Pricing, Technical, *and* Legal. The
   team assembles itself to fit the request.
2. Each **specialist** drafts its section and hands it back.
3. A **Reviewer** red-teams every section and pushes weak work back for revision -
   a real review loop, not a rubber stamp.
4. A **human is pulled into the room** for approval whenever a discount exceeds 20%
   or the total breaks the customer's budget.
5. The Coordinator assembles one clean, final proposal.

## Why Band is the core, not a wrapper

Remove Band and this system cannot function. Every part of the workflow is a Band
primitive:

- **Discovery & recruitment** - the Coordinator uses Band's peer lookup and
  `add_participant` to assemble its team live, based on the RFP content.
- **All coordination is @mention routing** - delegation, the review loop, the
  human-approval escalation, and hand-offs are all Band messages between participants.
- **The room is the workspace** - humans and agents share one space; the human can
  step in at any point. There is no separate backend orchestrator, Band *is* the
  orchestration layer.

## The agents

| Agent | Recruited when… | Role |
|-------|-----------------|------|
| **Coordinator** | always (entry point) | Reads RFP, recruits specialists, routes review, enforces business rules, assembles final proposal |
| **Pricing Specialist** | RFP mentions price/budget/discount | Itemized, budget-aware pricing proposal |
| **Technical Specialist** | RFP mentions architecture/integrations/security | Technical solution mapped to each requirement |
| **Legal Specialist** | RFP mentions contracts/compliance/SLA/GDPR | Compliance coverage + proposed contract terms |
| **Reviewer** | always (quality gate) | Adversarial red-team across all sections |

Built cross-framework on Band's adapter system; all models run via AI/ML API.

## Business rules (human-in-the-loop)

- **Discount > 20%** - Coordinator halts and requests human approval in the room.
- **Total > stated budget** - Coordinator sends it back to Pricing to revise.

## Quick start

```bash
uv sync                                          # install dependencies
cp .env.example .env                             # add your AI/ML API key
cp agent_config.example.yaml agent_config.yaml   # add agent UUIDs + keys

# verify one agent connects:
uv run python verify_setup.py                    #  "Connected as: Coordinator"

# run each agent in its own terminal:
uv run python agents/coordinator.py
uv run python agents/specialist.py pricing_agent
uv run python agents/specialist.py technical_agent
uv run python agents/specialist.py legal_agent
uv run python agents/reviewer.py
```

Then in Band, create a room with the **Coordinator + Reviewer + you** (leave the
specialists out — the Coordinator recruits them), and send:

```
@Coordinator Please handle this RFP: ...
```

See `sample_rfp.md` and `sample_rfp_escalation.md` for ready-to-use test RFPs.

## Project structure

```
deal-desk/
├── agents/
│   ├── coordinator.py      # recruits, routes, enforces rules, finalizes
│   ├── specialist.py       # runs pricing_agent | technical_agent | legal_agent
│   └── reviewer.py         # adversarial quality gate
├── prompts.py              # all agent roles (the brains - edit here)
├── verify_setup.py         # connection smoke test
├── sample_rfp.md           # standard test RFP
├── sample_rfp_escalation.md# RFP that triggers human approval
├── .env.example
└── agent_config.example.yaml
```

## Built with

Band SDK (`band`) · LangGraph · AI/ML API (GPT-4o) · Python 3.12


## Demo Video 

Watch the demo here :
[ Demo Video ](https://drive.google.com/file/d/1RVQwgcvrxsLRm7oe2oxYmchXrwiBAGhd/view?usp=sharing)
