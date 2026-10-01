# Simple Database Toolkit: public source

The downloadable Windows release includes all eight tools, including the BML
skinset and material editor. The BML editor implementation is maintained
separately and is excluded from this source distribution. Building this source
produces a SourceEdition executable with seven tools; it cannot reproduce the
complete release binary.

## Development

See the repository's ReadMe.md for GUI enhancements, all eight release tools,
runway heading behavior, backups, and installation instructions. Release changes
are recorded in CHANGELOG.md.

Run Setup_Environment.cmd, then Launch_Simple_Database_Toolkit.cmd from this
folder. The setup script uses %USERPROFILE%\.venvs\sdt. From this folder:

```powershell
& "$env:USERPROFILE\.venvs\sdt\Scripts\python.exe" -m pytest
& "$env:USERPROFILE\.venvs\sdt\Scripts\python.exe" -m PyInstaller SimpleDatabaseToolkit_v2.2.spec
```

Services, domain models, UI, and workers are in src/simple_database_toolkit/.
Tests use temporary files. Installed theater validation is opt-in:

```powershell
& "$env:USERPROFILE\.venvs\sdt\Scripts\python.exe" tools/validate_theater_xml.py `
  --objects "<BMS Objects folder>" --report artifacts/theater-validation.json
```

The audit reads installed XML and hashes it before and after testing. Service
edits use temporary copies and verify backup restoration. Generated outputs,
environments, and game data do not belong in source control. Older releases'
legacy source remains at the repository root.

## Distribution

PUBLIC_SOURCE_MANIFEST.json records the SHA-256 hashes of this reviewed source
export. Public release bundles are built from the full local workspace and
uploaded as release assets separately from source commits. Keeping Python source
out of Git does not prevent reverse engineering of distributed bytecode.
