"""Compare live user messages with and without a LangGraph checkpointer."""

import argparse
import operator
import os
from pathlib import Path
from typing import Annotated, TypedDict
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


SYSTEM_PROMPT = (
    "Use only the supplied conversation to answer. Reply briefly. "
    "If a requested fact is missing, say you do not have that information. "
    "Do not invent missing facts."
)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]


def build_graphs(model: ChatOpenAI):
    def chatbot(state: AgentState) -> AgentState:
        history = state["messages"]
        print(f"Conversation messages sent: {len(history)}")
        for message in history:
            print(f"  {message.type}: {message.content}")
        response = model.invoke([SystemMessage(content=SYSTEM_PROMPT), *history])
        return {"messages": [response]}

    builder = StateGraph(AgentState)
    builder.add_node("chatbot", chatbot)
    builder.add_edge(START, "chatbot")
    builder.add_edge("chatbot", END)

    without_memory = builder.compile()
    with_memory = builder.compile(checkpointer=InMemorySaver())
    return without_memory, with_memory


def show_response(response: AIMessage) -> None:
    print(f"AI: {response.content}")
    print(f"OpenAI response ID: {response.response_metadata.get('id', 'not returned')}")
    usage = response.usage_metadata or {}
    print(
        f"Tokens: input={usage.get('input_tokens', 'not returned')}, "
        f"output={usage.get('output_tokens', 'not returned')}"
    )


def run_demo(model: ChatOpenAI) -> None:
    without_memory, with_memory = build_graphs(model)
    thread_id = str(uuid4())
    print("\nType a message at You:. Both versions receive the same new message.")
    print("Use /reset for a new conversation. Use /quit to stop.")
    print(f"Memory thread: {thread_id}")
    while True:
        prompt = input("\nYou: ").strip()
        if not prompt:
            continue
        if prompt == "/quit":
            return
        if prompt == "/reset":
            thread_id = str(uuid4())
            print(f"New empty memory thread: {thread_id}")
            continue
        for label, graph, graph_config in (
            ("WITHOUT MEMORY", without_memory, None),
            ("WITH MEMORY", with_memory, {"configurable": {"thread_id": thread_id}}),
        ):
            print(f"\n{label}\n{'=' * 60}")
            result = graph.invoke(
                {"messages": [HumanMessage(content=prompt)]}, config=graph_config
            )
            show_response(result["messages"][-1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="Override the OpenAI model ID.")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parent / ".env")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        parser.exit(2, "Missing OPENAI_API_KEY. Configure .env as described in README.md.\n")
    model_id = args.model or os.getenv("OPENAI_MODEL") or "gpt-5.4-nano"
    print(f"LIVE DEMO: {model_id}. Each message makes two OpenAI API calls.")
    model = ChatOpenAI(
        model=model_id,
        base_url="https://api.openai.com/v1",
        api_key=api_key,
        max_completion_tokens=1024,
        use_responses_api=False,
        store=False,
        timeout=45,
        max_retries=0,
    )
    try:
        run_demo(model)
    except (KeyboardInterrupt, EOFError):
        print("\nDemo closed.")


if __name__ == "__main__":
    main()
