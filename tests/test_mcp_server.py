import asyncio

from backend.mcp_server import mcp


def test_mcp_exposes_tool_resource_and_prompt():
    tools = asyncio.run(mcp.list_tools())
    resources = asyncio.run(mcp.list_resource_templates())
    prompts = asyncio.run(mcp.list_prompts())

    assert {tool.name for tool in tools} >= {
        "search_report_sections",
        "get_report_catalog",
    }
    assert any("report://" in str(resource.uri_template) for resource in resources)
    assert any(prompt.name == "grounded_report_qa" for prompt in prompts)
