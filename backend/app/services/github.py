import re
import base64
from typing import List, Dict, Optional, Any
import httpx

class GitHubService:
    def __init__(self):
        self.base_url = "https://api.github.com"

    def _get_headers(self, token: str, accept: str = "application/vnd.github.v3+json") -> Dict[str, str]:
        # Use "token" prefix universally — it works for classic PATs (ghp_),
        # fine-grained PATs (github_pat_), and OAuth app tokens (gho_) on all
        # GitHub API endpoints including write operations (Contents, Pulls, etc.).
        return {
            "Authorization": f"token {token}",
            "Accept": accept,
            "User-Agent": "ReviewPilot-App"
        }

    async def fetch_pr_details(self, owner: str, repo: str, pr_number: int, token: str) -> Dict[str, Any]:
        """Fetch general metadata for a specific pull request."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(token), timeout=10.0)
            response.raise_for_status()
            return response.json()

    async def fetch_pr_diff(self, owner: str, repo: str, pr_number: int, token: str) -> str:
        """Fetch the raw git diff text of a pull request."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        # Requesting application/vnd.github.v3.diff returns the raw unified diff format
        headers = self._get_headers(token, accept="application/vnd.github.v3.diff")
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            return response.text

    async def fetch_file_content(self, owner: str, repo: str, path: str, ref: str, token: str) -> str:
        """Fetch the content of a specific file at a given commit/branch reference."""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(token), params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            # GitHub returns base64 encoded content for files
            content_b64 = data.get("content", "")
            # Remove line breaks
            content_b64 = content_b64.replace("\n", "").replace("\r", "")
            return base64.b64decode(content_b64).decode("utf-8", errors="ignore")

    async def search_repository(self, owner: str, repo: str, query: str, token: str) -> List[Dict[str, Any]]:
        """Search for code patterns inside the repository codebase."""
        url = f"{self.base_url}/search/code"
        # Scope search query to the repository
        scoped_query = f"{query} repo:{owner}/{repo}"
        params = {"q": scoped_query}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(token), params=params, timeout=15.0)
            if response.status_code == 422:
                # Search query unprocessable (often empty query or bad formatting)
                return []
            response.raise_for_status()
            items = response.json().get("items", [])
            return [
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "git_url": item.get("git_url"),
                    "sha": item.get("sha"),
                }
                for item in items
            ]

    async def get_related_files(self, owner: str, repo: str, path: str, ref: str, token: str) -> List[str]:
        """Crawl the imports/requirements of a file to return potential context files."""
        try:
            content = await self.fetch_file_content(owner, repo, path, ref, token)
        except Exception:
            return []

        # Find import patterns (JS/TS, Python, Go etc.)
        related_paths = []
        
        # Python: import xyz, from xyz import abc
        py_imports = re.findall(r'^(?:import|from)\s+([a-zA-Z0-9_\.]+)', content, re.MULTILINE)
        # JS/TS: import ... from 'xyz', require('xyz')
        js_imports = re.findall(r'(?:import|from|require)\(?\s*[\'"]([^\'\"]+)[\'"]', content)
        
        candidates = list(set(py_imports + js_imports))
        
        # Convert modules to potential local file paths and check if they exist or search them
        for candidate in candidates:
            # Skip standard libraries / node_modules if obvious
            if candidate.startswith((".", "/")):
                # Resolve relative path base
                base_dir = "/".join(path.split("/")[:-1])
                clean_path = candidate.lstrip("./")
                possible_path = f"{base_dir}/{clean_path}" if base_dir else clean_path
                related_paths.append(possible_path)
            else:
                # Check if we can search for the candidate file in the repo
                search_results = await self.search_repository(owner, repo, f"filename:{candidate}", token)
                for item in search_results:
                    related_paths.append(item["path"])
                    
        # Filter duplicates and return
        return list(set(related_paths))[:5]  # Limit to top 5 related files to save tokens

    async def post_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        commit_id: str,
        path: str,
        line: int,
        body: str,
        token: str
    ) -> Dict[str, Any]:
        """Post an inline review comment on a specific line of a file in the PR."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        payload = {
            "body": body,
            "commit_id": commit_id,
            "path": path,
            "line": line,
            "side": "RIGHT"  # Comments on the modified side of the diff
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self._get_headers(token), json=payload, timeout=10.0)
            response.raise_for_status()
            return response.json()

    async def post_summary_comment(self, owner: str, repo: str, pr_number: int, body: str, token: str) -> Dict[str, Any]:
        """Post a high-level review report comment on the pull request thread."""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        payload = {"body": body}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self._get_headers(token), json=payload, timeout=10.0)
            response.raise_for_status()
            return response.json()

    async def fetch_file_metadata(self, owner: str, repo: str, path: str, ref: str, token: str) -> Dict[str, Any]:
        """Fetch file metadata including content text and the current blob SHA from GitHub."""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers(token), params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            content_b64 = data.get("content", "")
            content_b64 = content_b64.replace("\n", "").replace("\r", "")
            text_content = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
            
            return {
                "content": text_content,
                "sha": data.get("sha")
            }

    async def update_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        branch: str,
        content: str,
        sha: str,
        message: str,
        token: str
    ) -> Dict[str, Any]:
        """Update a specific file content at a given branch reference on GitHub."""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "sha": sha,
            "branch": branch
        }
        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=self._get_headers(token), json=payload, timeout=10.0)
            response.raise_for_status()
            return response.json()

github_service = GitHubService()
