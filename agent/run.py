"""Run the open-satellite-analysis skill with a LangChain Deep Agent on a ChatGPT-authenticated Codex model.

One-time login: uv run python -c "from langchain_openai.chatgpt_oauth import login_chatgpt; login_chatgpt()"

Usage: uv run python agent/run.py <workdir> "<question>" [--model gpt-6-luna] [--effort low|medium|high]

The agent loads skills/open-satellite-analysis/SKILL.md, runs the scripts in <workdir>, and ends with an answer.
answer.md holds that answer, run.json the time, tool calls and tokens.
"""

import argparse
import json
import time
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_openai.chat_models.codex import _ChatOpenAICodex

ROOT = Path(__file__).resolve().parent.parent

SYSTEM = """You answer questions about places on Earth from satellite data. File tools and shell commands both use
the real absolute paths given in the task. Work without asking questions; nobody will answer. Finish with a short
answer: the numbers, the dates of the scenes used, how much of the area was visible, the files that show it, and
the limits that apply."""


def tokens(handler):
    total = {"input": 0, "cached": 0, "output": 0}
    for u in handler.usage_metadata.values():
        total["input"] += u.get("input_tokens", 0)
        total["cached"] += (u.get("input_token_details") or {}).get("cache_read", 0)
        total["output"] += u.get("output_tokens", 0)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("question")
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--effort", choices=["low", "medium", "high"], help="reasoning effort (model default if unset)")
    args = ap.parse_args()

    work = Path(args.workdir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    skills = ROOT / "skills"
    usage = UsageMetadataCallbackHandler()
    reasoning = {"reasoning": {"effort": args.effort}} if args.effort else {}
    model = _ChatOpenAICodex(model=args.model, callbacks=[usage], **reasoning)

    agent = create_deep_agent(
        model=model,
        system_prompt=SYSTEM,
        skills=[str(skills)],
        # virtual_mode=False and absolute paths: otherwise the agent cannot find the skill scripts
        backend=LocalShellBackend(root_dir=work, virtual_mode=False, timeout=600, inherit_env=True),
    )
    task = (
        f"{args.question}\n\nUse the open-satellite-analysis skill (SKILL_DIR is {skills / 'open-satellite-analysis'}). "
        f"Use {work} as the work directory for every file you write."
    )
    start = time.time()
    result = agent.invoke({"messages": [{"role": "user", "content": task}]}, config={"recursion_limit": 200})
    elapsed = time.time() - start

    messages = result["messages"]
    answer = messages[-1].text
    (work / "answer.md").write_text(f"**Question:** {args.question}\n\n{answer}\n")
    total = tokens(usage)
    meta = {
        "question": args.question,
        "model": args.model,
        "effort": args.effort,
        "harness": "deepagents",
        "seconds": round(elapsed),
        "tool_calls": sum(len(getattr(m, "tool_calls", None) or []) for m in messages),
        "input_tokens": total["input"],
        "cached_tokens": total["cached"],
        "output_tokens": total["output"],
    }
    (work / "run.json").write_text(json.dumps(meta, indent=2))
    print(answer)
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
