# Tools

This directory contains Python scripts for deterministic execution.

## What Goes in a Tool

Tools are Python scripts that:
- Handle API calls
- Process data
- Transform files
- Execute specific tasks reliably

## Design Principles

1. **Single Responsibility**: Each tool does one thing well
2. **Clear Inputs/Outputs**: Use command-line arguments or config files
3. **Error Handling**: Return clear error messages
4. **Idempotent**: Running twice should be safe
5. **Testable**: Easy to verify behavior

## Example Structure

```python
#!/usr/bin/env python3
"""
Tool: [Name]
Description: What this tool does
"""

import os
from dotenv import load_dotenv

load_dotenv()

def main():
    # Tool logic here
    pass

if __name__ == "__main__":
    main()
```

## Best Practices

- Load environment variables from `.env`
- Use type hints for clarity
- Add docstrings to functions
- Log important steps
- Return meaningful exit codes
