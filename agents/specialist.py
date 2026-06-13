import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent
from band.adapters import LangGraphAdapter
from band.config import load_agent_config

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts import PRICING_SPECIALIST, TECHNICAL_SPECIALIST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROLE_PROMPTS = {
    "pricing_agent": PRICING_SPECIALIST,
    "technical_agent": TECHNICAL_SPECIALIST,
}


async def main(config_name: str):
    load_dotenv()

    if config_name not in ROLE_PROMPTS:
        raise SystemExit(
            f"Unknown specialist '{config_name}'. "
            f"Choose one of: {', '.join(ROLE_PROMPTS)}"
        )

    agent_id, api_key = load_agent_config(config_name)

    llm = ChatOpenAI(
        model="gpt-4o",
        base_url=os.getenv("AIML_BASE_URL"),
        api_key=os.getenv("AIML_API_KEY"),
    )

    adapter = LangGraphAdapter(
        llm=llm,
        checkpointer=InMemorySaver(),
        custom_section=ROLE_PROMPTS[config_name],
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("THENVOI_WS_URL"),
        rest_url=os.getenv("THENVOI_REST_URL"),
    )

    logger.info(f"Specialist '{config_name}' is running. Press Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: python agents/specialist.py <pricing_agent|technical_agent>"
        )
    asyncio.run(main(sys.argv[1]))