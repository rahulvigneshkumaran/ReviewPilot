import sys
import json
import asyncio
from typing import Dict, Any

from app.services.github import github_service

# Redirect all normal print calls to stderr to keep stdout purely for JSON-RPC messages
def log(msg: str):
    sys.stderr.write(f"[ReviewPilot-MCP] {msg}\n")
    sys.stderr.flush()

TOOLS = [
    {
        "name": "get_pr_diff",
        "description": "Fetch the raw unified diff text of a GitHub pull request.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner username"},
                "repo": {"type": "string", "description": "Repository name"},
                "pr_number": {"type": "integer", "description": "Pull request number"},
                "token": {"type": "string", "description": "GitHub OAuth access token"}
            },
            "required": ["owner", "repo", "pr_number", "token"]
        }
    },
    {
        "name": "get_file_content",
        "description": "Fetch the raw text contents of a file at a specific reference (commit or branch).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string", "description": "Relative file path in the repository"},
                "ref": {"type": "string", "description": "Commit SHA or branch reference name"},
                "token": {"type": "string"}
            },
            "required": ["owner", "repo", "path", "ref", "token"]
        }
    },
    {
        "name": "search_repository",
        "description": "Search code files in the repository for specific queries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "query": {"type": "string", "description": "Search query terms or patterns"},
                "token": {"type": "string"}
            },
            "required": ["owner", "repo", "query", "token"]
        }
    },
    {
        "name": "get_related_files",
        "description": "Examine imports/requirements in a file to return potential related workspace files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "path": {"type": "string", "description": "File path to examine dependencies for"},
                "ref": {"type": "string", "description": "Commit reference name"},
                "token": {"type": "string"}
            },
            "required": ["owner", "repo", "path", "ref", "token"]
        }
    },
    {
        "name": "post_review_comment",
        "description": "Post an inline code review comment on a specific line of a file in a PR.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pr_number": {"type": "integer"},
                "commit_id": {"type": "string", "description": "Commit SHA hash where review comment is posted"},
                "path": {"type": "string", "description": "File path where code issue was found"},
                "line": {"type": "integer", "description": "Line number (1-indexed) in the diff hunk"},
                "body": {"type": "string", "description": "Review comment body markdown content"},
                "token": {"type": "string"}
            },
            "required": ["owner", "repo", "pr_number", "commit_id", "path", "line", "body", "token"]
        }
    },
    {
        "name": "post_summary_comment",
        "description": "Post a high-level review report or comment on a pull request thread.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
                "pr_number": {"type": "integer"},
                "body": {"type": "string", "description": "Markdown text summary content report"},
                "token": {"type": "string"}
            },
            "required": ["owner", "repo", "pr_number", "body", "token"]
        }
    }
]

async def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the core GitHub client action mapping the MCP tool request."""
    try:
        if name == "get_pr_diff":
            res = await github_service.fetch_pr_diff(
                arguments["owner"], arguments["repo"], int(arguments["pr_number"]), arguments["token"]
            )
            return {"content": [{"type": "text", "text": res}]}
            
        elif name == "get_file_content":
            res = await github_service.fetch_file_content(
                arguments["owner"], arguments["repo"], arguments["path"], arguments["ref"], arguments["token"]
            )
            return {"content": [{"type": "text", "text": res}]}
            
        elif name == "search_repository":
            res = await github_service.search_repository(
                arguments["owner"], arguments["repo"], arguments["query"], arguments["token"]
            )
            return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
            
        elif name == "get_related_files":
            res = await github_service.get_related_files(
                arguments["owner"], arguments["repo"], arguments["path"], arguments["ref"], arguments["token"]
            )
            return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
            
        elif name == "post_review_comment":
            res = await github_service.post_review_comment(
                arguments["owner"],
                arguments["repo"],
                int(arguments["pr_number"]),
                arguments["commit_id"],
                arguments["path"],
                int(arguments["line"]),
                arguments["body"],
                arguments["token"]
            )
            return {"content": [{"type": "text", "text": f"Comment posted. ID: {res.get('id', 'unknown')}"}]}
            
        elif name == "post_summary_comment":
            res = await github_service.post_summary_comment(
                arguments["owner"], arguments["repo"], int(arguments["pr_number"]), arguments["body"], arguments["token"]
            )
            return {"content": [{"type": "text", "text": f"Summary comment posted. ID: {res.get('id', 'unknown')}"}]}
            
        else:
            return {"isError": True, "content": [{"type": "text", "text": f"Tool '{name}' not found."}]}
            
    except Exception as e:
        log(f"Error executing tool '{name}': {str(e)}")
        return {"isError": True, "content": [{"type": "text", "text": f"Execution error: {str(e)}"}]}

async def main():
    log("MCP Server running in stdio mode...")
    
    # Read stdin lines asynchronously
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break
            
        try:
            request = json.loads(line.decode("utf-8"))
            jsonrpc = request.get("jsonrpc")
            method = request.get("method")
            req_id = request.get("id")
            
            if jsonrpc != "2.0":
                continue
                
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "reviewpilot-mcp",
                            "version": "1.0.0"
                        }
                    }
                }
                
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": TOOLS
                    }
                }
                
            elif method == "tools/call":
                params = request.get("params", {})
                name = params.get("name")
                arguments = params.get("arguments", {})
                
                log(f"Received call for tool '{name}'")
                result = await handle_tool_call(name, arguments)
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": result
                }
                
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
                
            # Write response JSON line to stdout
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        except Exception as e:
            log(f"Error parsing incoming JSON-RPC frame: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
