# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os

# PDF tooling on the development host supplies an incompatible ICU DLL with
# the same filename as Windows ICU. This app does not use Poppler.
os.environ['PATH'] = os.pathsep.join(
    directory for directory in os.environ.get('PATH', '').split(os.pathsep)
    if '/poppler/' not in directory.replace('\\', '/').lower()
)
profile = {}
exec((Path(SPECPATH) / 'src/simple_database_toolkit/build_profile.py').read_text(encoding='utf-8'), profile)
full_build = profile['BML_EDITOR_ENABLED']
if full_build:
    for module in ('services/bml_service.py', 'ui/pages/bml_page.py'):
        if not (Path(SPECPATH) / 'src/simple_database_toolkit' / module).is_file():
            raise SystemExit('Full release requires the local BML editor source: ' + module)
bundle_name = 'SimpleDatabaseToolkit_v2.2' if full_build else 'SimpleDatabaseToolkit_v2.2_SourceEdition'

a = Analysis(
    ['app.py'],
    pathex=['src'],
    binaries=[],
    datas=[('../Media', 'Media'), ('src/simple_database_toolkit/ui/styles', 'simple_database_toolkit/ui/styles')],
    hiddenimports=['simple_database_toolkit.services.bml_service', 'simple_database_toolkit.ui.pages.bml_page'] if full_build else [],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
if any('/poppler/' in entry[1].replace('\\', '/').lower() for entry in a.binaries):
    raise SystemExit('Unexpected Poppler DLL in application bundle; rebuild with --clean.')
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=bundle_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=bool(os.environ.get('SDT_BUILD_CONSOLE')),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['../Media/128_Icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=bundle_name,
)
