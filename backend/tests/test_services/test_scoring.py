import pytest
from app.services.scoring import calculate_pr_risk
from app.db.models import SeverityLevel

def test_calculate_pr_risk_base():
    """Verify that a PR with no issues, small size, and non-sensitive files scores 0 (LOW)."""
    score, category = calculate_pr_risk([], {"changed_lines": {"src/main.py": [1, 2]}})
    assert score == 0
    assert category == "LOW"

def test_calculate_pr_risk_issue_weights():
    """Verify issue severity weights accumulation (+35 Critical, +20 High, +10 Med, +5 Low)."""
    issues = [
        {"severity": "LOW"},
        {"severity": "MEDIUM"},
        {"severity": "HIGH"},
        {"severity": "CRITICAL"},
        # Test mapping an enum value as well
        {"severity": SeverityLevel.CRITICAL}
    ]
    # Sum: 5 (Low) + 10 (Med) + 20 (High) + 35 (Critical) + 35 (Critical enum) = 105
    # Normalization should cap it at 100
    score, category = calculate_pr_risk(issues, {"changed_lines": {"src/main.py": [1]}})
    assert score == 100
    assert category == "CRITICAL"

def test_calculate_pr_risk_large_pr():
    """Verify large PR penalty (>500 lines changed adds +10)."""
    # Create changes with > 500 lines
    changed_lines = {
        "src/main.py": list(range(1, 502))  # 501 lines
    }
    score, category = calculate_pr_risk([], {"changed_lines": changed_lines})
    assert score == 10  # 0 base + 10 large PR
    assert category == "LOW"

def test_calculate_pr_risk_sensitive_files():
    """Verify sensitive file modification penalty (+10)."""
    # 1. Config file
    score, category = calculate_pr_risk([], {"changed_lines": {"config/production.json": [1]}})
    assert score == 10
    
    # 2. Database migration
    score, category = calculate_pr_risk([], {"changed_lines": {"db/migrations/env.py": [1]}})
    assert score == 10
    
    # 3. Security module
    score, category = calculate_pr_risk([], {"changed_lines": {"app/auth/security.py": [1]}})
    assert score == 10

    # 4. Yaml deployment config
    score, category = calculate_pr_risk([], {"changed_lines": {"deploy/values.yaml": [1]}})
    assert score == 10

def test_calculate_pr_risk_combination_and_cap():
    """Verify that combinations of penalties sum correctly and cap at 100."""
    issues = [
        {"severity": "HIGH"},    # +20
        {"severity": "MEDIUM"},  # +10
    ]
    changed_lines = {
        "config/settings.py": list(range(1, 600))  # sensitive (+10) and large (+10)
    }
    # Sum: 20 + 10 + 10 + 10 = 50
    score, category = calculate_pr_risk(issues, {"changed_lines": changed_lines})
    assert score == 50
    assert category == "MEDIUM"

    # Add a critical security issue to push it to CRITICAL
    issues.append({"severity": "CRITICAL"})  # +35 (Sum: 85)
    score, category = calculate_pr_risk(issues, {"changed_lines": changed_lines})
    assert score == 85
    assert category == "CRITICAL"
