# Repository Guidelines

## Project Structure

The PySide6 application starts at root app.py. In src/simple_database_toolkit/,
services/ handles file operations, domain/ contains models, ui/ contains Qt
widgets and themes, and workers/ executes long operations. Tests live in
tests/services/, tests/ui/, and tests/integration/. Media/ contains artwork.
Treat build/, dist/, artifacts/, and caches as generated output.

## Build, Test, and Development Commands

Run Setup_Environment.cmd from the repository root to install development and
build dependencies into %USERPROFILE%\.venvs\sdt. Launch with
Launch_Simple_Database_Toolkit.cmd. Using that environment's python.exe, run
-m pytest for all tests or -m PyInstaller SimpleDatabaseToolkit_v2.2.spec to
build the seven-tool SourceEdition Windows bundle.

## Coding and Testing Conventions

Use four-space indentation, type hints on public interfaces, snake_case modules
and functions, PascalCase classes, and uppercase constants. Match nearby code;
no formatter or linter is configured. Keep Qt updates on the main thread and
long operations in workers. Use pytest test_*.py files and test_<behavior>
functions. Cover writes, cancellation, rollback, and unchanged-data guarantees
with tmp_path fixtures. Installed-data tests require --bms-objects and edit only
temporary copies. Coverage is configured without a minimum threshold.

## Safety and Distribution

Preserve file formatting, validate before writes, use atomic replacement and
multi-file rollback, and recheck inputs before applying previews. Keep Qt updates
on the main thread. Public source intentionally excludes the BML editor;
downloadable release binaries include it. Do not commit its implementation,
generated bundles, or game data. PUBLIC_SOURCE_MANIFEST.json records reviewed
export hashes; coordinate public changes with the full workspace maintainer.

## Commits and Pull Requests

Use short, imperative subjects such as Fix runway heading validation. Describe
affected tools and file formats, link issues where relevant, list tests run,
and include screenshots for GUI changes. Run the full pytest suite before
submitting.
