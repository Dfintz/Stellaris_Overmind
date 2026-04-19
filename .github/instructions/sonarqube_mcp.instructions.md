---
applyTo: "**/*"
---

These are guidelines for using the SonarQube MCP server.

# Important Tool Guidelines

## Basic usage
- **IMPORTANT**: After finishing generating or modifying any code files, you MUST call the `analyze_file_list` tool (if it exists) to analyze the files you created or modified.
- **IMPORTANT**: When starting a new task, you MUST disable automatic analysis with the `toggle_automatic_analysis` tool if it exists.
- **IMPORTANT**: When done generating code, you MUST re-enable automatic analysis with the `toggle_automatic_analysis` tool if it exists.

## Code Language Detection
- When analyzing code snippets, detect the programming language from syntax
- If unclear, ask the user or make an educated guess

## Code Issues and Violations
- After fixing issues, do not attempt to verify them using `search_sonar_issues_in_projects`, as the server will not yet reflect the updates
