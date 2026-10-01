# Repository Guidelines

## Structure

Modern development belongs in UI_rework_SimpleDatabase_Toolkit/. Services handle
files, domain contains models, ui contains Qt widgets, and workers execute long
operations. Preserve the legacy application at the repository root.

## Development and Testing

Run Setup_Environment.cmd, then use %USERPROFILE%\.venvs\sdt\Scripts\python.exe
to launch app.py or run -m pytest from the modern project folder. Installed-data
tests require --bms-objects and always edit temporary copies. Keep Python code
at four-space indentation with snake_case functions and PascalCase classes.

## Safety and Distribution

Preserve file formatting, validate before writes, use atomic replacement and
multi-file rollback, and recheck inputs before applying previews. Keep Qt updates
on the main thread. Public source intentionally excludes the BML editor;
downloadable release binaries include it. Do not commit its implementation,
generated bundles, or game assets. Describe affected tools and tests in pull
requests and include screenshots for UI changes.
