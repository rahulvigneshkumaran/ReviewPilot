import json
import pytest
from unittest.mock import AsyncMock, patch

from app.services.mcp import TOOLS, handle_tool_call

def test_mcp_tools_registration():
    """Verify all 6 mandatory review tools are registered in the MCP manifest."""
    tool_names = {t["name"] for t in TOOLS}
    required_tools = {
        "get_pr_diff",
        "get_file_content",
        "search_repository",
        "get_related_files",
        "post_review_comment",
        "post_summary_comment"
    }
    assert required_tools.issubset(tool_names)

@pytest.mark.asyncio
async def test_mcp_get_pr_diff(mocker):
    """Verify handle_tool_call resolves get_pr_diff using github_service."""
    mock_fetch = mocker.patch("app.services.github.github_service.fetch_pr_diff", new_callable=AsyncMock)
    mock_fetch.return_value = "--- a/main.py\n+++ b/main.py\n@@ -1,1 +1,2 @@"

    args = {
        "owner": "test-owner",
        "repo": "test-repo",
        "pr_number": 5,
        "token": "gho_testtoken"
    }
    
    result = await handle_tool_call("get_pr_diff", args)
    
    # Assert return structure matches MCP spec
    assert "content" in result
    assert result["content"][0]["type"] == "text"
    assert "--- a/main.py" in result["content"][0]["text"]
    
    # Verify github_service called with exact arguments
    mock_fetch.assert_called_once_with("test-owner", "test-repo", 5, "gho_testtoken")

@pytest.mark.asyncio
async def test_mcp_post_review_comment(mocker):
    """Verify handle_tool_call resolves post_review_comment using github_service."""
    mock_post = mocker.patch("app.services.github.github_service.post_review_comment", new_callable=AsyncMock)
    mock_post.return_value = {"id": 123456}

    args = {
        "owner": "owner",
        "repo": "repo",
        "pr_number": 12,
        "commit_id": "sha123",
        "path": "app.py",
        "line": 10,
        "body": "Fix this code smell",
        "token": "token"
    }

    result = await handle_tool_call("post_review_comment", args)
    
    assert "content" in result
    assert "Comment posted. ID: 123456" in result["content"][0]["text"]
    
    mock_post.assert_called_once_with("owner", "repo", 12, "sha123", "app.py", 10, "Fix this code smell", "token")

@pytest.mark.asyncio
async def test_mcp_unknown_tool():
    """Verify calling an unknown tool returns an error content frame."""
    result = await handle_tool_call("invalid_tool_name", {})
    assert result.get("isError") is True
    assert "Tool 'invalid_tool_name' not found." in result["content"][0]["text"]
