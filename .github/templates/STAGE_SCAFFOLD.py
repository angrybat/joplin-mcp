"""
Scaffold stage implementation. Copy this and customize for your stage.

Steps:
1. Copy this file to dagger/src/joplin_mcp/__init__.py as a new method (or append to existing).
2. Copy SCAFFOLD_SCRIPT below to src/scripts/your_stage_name.py.
3. Update all SCAFFOLD_* placeholders with your stage name and logic.
4. Test: dagger call your-stage-name --source=.
5. Update PLAN.md with stage contract and success criteria.
6. Add entry to Progress Ledger when complete.
"""

# =============================================================================
# DAGGER MODULE: dagger/src/joplin_mcp/__init__.py
# =============================================================================

# Option A: Stage that READS repository files (requires source directory)
# @function
# async def your_stage_name(self, source: dagger.Directory) -> dagger.Directory:
#     """
#     Stage: your-stage-name
#     SCAFFOLD_DESCRIPTION
#
#     Inputs:
#     - source: repository root directory
#
#     Outputs:
#     - SCAFFOLD_OUTPUT_DESCRIPTION
#     """
#     return (
#         dag.container()
#         .from_("python:3.12.9-slim")
#         .with_mounted_directory("/workspace", source)
#         .with_exec(
#             [
#                 "python",
#                 "/workspace/src/scripts/your_stage_name.py",
#                 "--input-root",
#                 "/workspace",
#                 "--output-root",
#                 "/tmp/your-stage-out",
#                 # Add other --flag arguments as needed
#             ]
#         )
#         .directory("/tmp/your-stage-out")
#     )
#
#
# Option B: Stage that ONLY RUNS EXTERNAL COMMANDS (no source directory needed)
# @function
# async def your_stage_name(self) -> dagger.Directory:
#     """
#     Stage: your-stage-name
#     SCAFFOLD_DESCRIPTION (e.g., "Build Docker image from external source")
#
#     Note: This stage does not require repository files; only runs external commands.
#
#     Outputs:
#     - SCAFFOLD_OUTPUT_DESCRIPTION
#     """
#     return (
#         dag.container()
#         .from_("python:3.12.9-slim")
#         .with_exec(["your-command", "--args"])
#         .directory("/output-path")
#     )


# =============================================================================
# STAGE SCRIPT: src/scripts/your_stage_name.py
# =============================================================================

"""Generate SCAFFOLD_DESCRIPTION from canonical inputs."""

from pathlib import Path
import argparse


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.
    
    Note: Only required when stage reads repository files.
    If stage only runs external commands, Dagger function (Option B) does not call script.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, help="Repository root (mounted at /workspace)")
    parser.add_argument("--output-root", required=True, help="Output directory path")
    # Add other arguments as needed
    return parser.parse_args()


def main() -> None:
    """Execute the stage.
    
    Only called when stage reads repository files (not for Option B: external-command-only stages).
    """
    args = parse_args()
    input_root = Path(args.input_root)
    output_root = Path(args.output_root)

    # Create output structure
    output_root.mkdir(parents=True, exist_ok=True)

    # SCAFFOLD_BUSINESS_LOGIC

    # Example:
    # source_files = input_root / "fixtures" / "definitions"
    # (output_root / "output").mkdir(parents=True, exist_ok=True)
    # ... process and write files ...


if __name__ == "__main__":
    main()
