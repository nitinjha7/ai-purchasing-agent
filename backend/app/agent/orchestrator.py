import json
from typing import Any

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.agent.prompts import SYSTEM_PROMPT, build_situation_prompt
from app.agent.tools import TOOL_FUNCTION_DECLARATIONS, dispatch_tool_call
from app.config import get_settings
from app.domain.models import AgentDecision

MAX_TURNS = 8


class AgentDecisionError(Exception):
    pass


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise AgentDecisionError(f"Model did not return a JSON object: {text!r}")
    return json.loads(text[start : end + 1])


def run_agent(
    db: Session,
    scenario_type: str,
    situation: dict,
    revision_note: str | None = None,
) -> tuple[AgentDecision, list[dict]]:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    tool = types.Tool(function_declarations=[
        types.FunctionDeclaration(**decl) for decl in TOOL_FUNCTION_DECLARATIONS
    ])

    situation_prompt = build_situation_prompt(scenario_type, situation)
    if revision_note:
        situation_prompt = f"{situation_prompt}\n\n{revision_note}"

    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=situation_prompt)]),
    ]
    tool_call_log: list[dict[str, Any]] = []

    for _ in range(MAX_TURNS):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[tool],
            ),
        )
        candidate = response.candidates[0]
        contents.append(candidate.content)

        function_calls = [part.function_call for part in candidate.content.parts if part.function_call]
        if not function_calls:
            text = "".join(part.text or "" for part in candidate.content.parts)
            decision_dict = _extract_json_object(text)
            return AgentDecision.model_validate(decision_dict), tool_call_log

        response_parts = []
        for call in function_calls:
            args = dict(call.args)
            result = dispatch_tool_call(db, call.name, args)
            tool_call_log.append({"tool": call.name, "args": args, "result": result})
            response_parts.append(types.Part(function_response=types.FunctionResponse(name=call.name, response=result)))
        contents.append(types.Content(role="user", parts=response_parts))

    raise AgentDecisionError(f"Agent did not converge on a decision within {MAX_TURNS} turns")
