#!/usr/bin/env python3
"""
Validate that all Dagger stages follow the standardized implementation pattern.

Pattern requirements:
- Single source directory input (no dag.host())
- No parent directory traversal (no source.directory(".."))
- Orchestration only in dagger/src/joplin_mcp/__init__.py
- Business logic in src/scripts/

Usage:
    python .github/scripts/validate-dagger-stage-pattern.py
"""

import sys
from pathlib import Path

# Forbidden patterns that indicate stage pattern violations
# These patterns are forbidden regardless of whether source is used
FORBIDDEN_PATTERNS = [
    ("dag.host()", "Use container mounting or source.directory() instead of dag.host()"),
    ('directory("..")', "Use source.directory() only; avoid parent traversal"),
    ("dag.current_module().source()", "Use source parameter instead of dag.current_module().source()"),
]

def check_file(filepath):
    """Check a file for forbidden patterns. Return (success, errors)."""
    errors = []
    content = filepath.read_text(encoding="utf-8")
    
    for pattern, reason in FORBIDDEN_PATTERNS:
        if pattern in content:
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if pattern in line:
                    errors.append(f"  Line {i}: {pattern} — {reason}")
    
    return len(errors) == 0, errors

def main():
    """Validate all Dagger stage implementations against forbidden patterns."""
    module_file = Path("dagger/src/joplin_mcp/__init__.py")
    
    if not module_file.exists():
        print("Error: dagger/src/joplin_mcp/__init__.py not found")
        return 1
    
    print("Validating Dagger stage pattern (forbidden patterns check)...")
    success, errors = check_file(module_file)
    
    if not success:
        print(f"✗ {module_file} contains forbidden patterns:")
        for error in errors:
            print(error)
        print("\nSee AGENTS.md 'Stage Implementation Pattern' for guidelines.")
        return 1
    
    print(f"✓ {module_file} passes forbidden patterns check")
    return 0

if __name__ == "__main__":
    sys.exit(main())
