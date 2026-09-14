"""Offline regression guards for the Gemini SDK tool wiring.

These require no network call and no real API key — the SDK validates the declarations
locally, which is exactly what previously broke (schema type casing and the role used for
the function-response turn).
"""

import inspect

import pytest
from google.genai import types

from app.agent import orchestrator
from app.agent.tools import TOOL_FUNCTION_DECLARATIONS, dispatch_tool_call


@pytest.mark.parametrize("decl", TOOL_FUNCTION_DECLARATIONS, ids=lambda d: d["name"])
def test_tool_declaration_is_accepted_by_the_sdk(decl):
    """Every declaration must construct a FunctionDeclaration without raising."""
    function_declaration = types.FunctionDeclaration(**decl)
    assert function_declaration.name == decl["name"]


def test_all_declarations_build_a_single_tool():
    tool = types.Tool(function_declarations=[types.FunctionDeclaration(**d) for d in TOOL_FUNCTION_DECLARATIONS])
    assert len(tool.function_declarations) == len(TOOL_FUNCTION_DECLARATIONS)


def test_every_declared_tool_is_dispatchable():
    """A declaration with no dispatch branch would only fail at runtime, mid-conversation."""
    declared = {d["name"] for d in TOOL_FUNCTION_DECLARATIONS}
    source = inspect.getsource(dispatch_tool_call)
    missing = [name for name in declared if f'"{name}"' not in source]
    assert missing == []


def test_function_response_turn_uses_the_user_role():
    """The Gemini SDK rejects role="tool"; function responses go back as a user turn."""
    source = inspect.getsource(orchestrator)
    assert 'role="tool"' not in source
    assert 'types.Content(role="user", parts=response_parts)' in source


def test_function_response_content_constructs():
    content = types.Content(
        role="user",
        parts=[types.Part(function_response=types.FunctionResponse(name="get_product_snapshot", response={"on_hand_qty": 1}))],
    )
    assert content.role == "user"
