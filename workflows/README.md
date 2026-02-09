# Workflows

This directory contains workflow definitions written as markdown SOPs (Standard Operating Procedures).

## What Goes in a Workflow

Each workflow should define:

1. **Objective**: What this workflow accomplishes
2. **Required Inputs**: What information/data is needed to start
3. **Tools Used**: Which scripts in `tools/` this workflow calls
4. **Expected Outputs**: What gets produced and where it goes
5. **Edge Cases**: Known issues, rate limits, error handling approaches

## Example Structure

```markdown
# Workflow: [Name]

## Objective
Brief description of what this accomplishes

## Required Inputs
- Input 1: description
- Input 2: description

## Tools Used
- `tools/script1.py`: What it does
- `tools/script2.py`: What it does

## Steps
1. First step
2. Second step
3. etc.

## Expected Outputs
- Output location and format

## Edge Cases
- Known issue 1 and how to handle it
- Rate limit handling
- etc.
```

## Tips

- Write workflows in plain language
- Update them as you learn better approaches
- Document failures and solutions
- Keep them focused on one objective
