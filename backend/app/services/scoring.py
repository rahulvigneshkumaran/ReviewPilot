import re
from typing import List, Dict, Any, Tuple

def calculate_pr_risk(issues: List[Any], files_metadata: Dict[str, Any]) -> Tuple[int, str]:
    """
    Calculate the risk score of a Pull Request (0-100) and return a risk category.
    
    Base Score: Starts at 0.
    Issue Penalties:
    - CRITICAL: +35 points
    - HIGH: +20 points
    - MEDIUM: +10 points
    - LOW: +5 points
    
    PR Metadata Penalties:
    - Large PR (>500 lines changed): +10 points
    - Sensitive file modifications (e.g. config, security, auth, database migrations): +10 points
    
    Normalization: Capped at 100.
    Category mappings:
    - 0-25: LOW
    - 26-50: MEDIUM
    - 51-75: HIGH
    - 76-100: CRITICAL
    """
    score = 0
    
    # 1. Issue Penalties
    for issue in issues:
        severity_str = "LOW"
        if isinstance(issue, dict):
            sev_val = issue.get("severity")
        else:
            sev_val = getattr(issue, "severity", None)
            
        if sev_val is not None:
            if hasattr(sev_val, "value"):
                severity_str = str(sev_val.value).upper()
            else:
                severity_str = str(sev_val).upper()
                
        if severity_str == "CRITICAL":
            score += 35
        elif severity_str == "HIGH":
            score += 20
        elif severity_str == "MEDIUM":
            score += 10
        elif severity_str == "LOW":
            score += 5
            
    # 2. PR Metadata Penalties
    total_lines = 0
    changed_files = []
    
    # Extract total lines changed and changed files from files_metadata
    if "total_lines_changed" in files_metadata:
        total_lines = files_metadata["total_lines_changed"]
    elif "changed_lines" in files_metadata:
        cl = files_metadata["changed_lines"] or {}
        total_lines = sum(len(lines) for lines in cl.values())
    else:
        # Check if files_metadata is the changed_lines dictionary itself
        try:
            if all(isinstance(v, list) for v in files_metadata.values()):
                total_lines = sum(len(lines) for lines in files_metadata.values())
        except Exception:
            pass

    if "changed_files" in files_metadata:
        changed_files = files_metadata["changed_files"]
    elif "changed_lines" in files_metadata:
        changed_files = list(files_metadata["changed_lines"].keys())
    else:
        # Check if files_metadata is the changed_lines dictionary itself
        try:
            if all(isinstance(v, list) for v in files_metadata.values()):
                changed_files = list(files_metadata.keys())
        except Exception:
            pass
            
    # Apply Large PR penalty (>500 lines changed)
    if total_lines > 500:
        score += 10
        
    # Apply Sensitive file modifications penalty (+10)
    sensitive_patterns = [
        r"config",
        r"settings",
        r"security",
        r"auth",
        r"db/migrations",
        r"alembic",
        r"dockerfile",
        r"kubernetes",
        r"k8s",
        r"\.github/workflows",
        r"pem",
        r"credential"
    ]
    
    has_sensitive = False
    for filepath in changed_files:
        filepath_lower = filepath.lower()
        if any(re.search(pat, filepath_lower) for pat in sensitive_patterns) or \
           filepath_lower.endswith(('.yml', '.yaml', '.ini', '.env', '.toml')) and \
           any(word in filepath_lower for word in ["config", "setting", "setup", "secret", "deploy"]):
            has_sensitive = True
            break
            
    if has_sensitive:
        score += 10
        
    # Cap score at 100
    score = min(score, 100)
    
    # Determine category
    if score <= 25:
        category = "LOW"
    elif score <= 50:
        category = "MEDIUM"
    elif score <= 75:
        category = "HIGH"
    else:
        category = "CRITICAL"
        
    return score, category
