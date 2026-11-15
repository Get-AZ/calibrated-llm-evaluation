# Install documentation without overwriting project files

Extract the ZIP to `docs` from the project root:

```powershell
Expand-Archive `
  -LiteralPath "$env:USERPROFILE\Downloads\Citation_Project_Documentation_v1.zip" `
  -DestinationPath .\docs `
  -ErrorAction Stop
```

This creates `docs\citation_project_documentation_v1\`. It does not replace an existing root README, modify the evaluation files, or publish anything. Review the draft README before copying it to a repository root. No repository URL is assumed.
