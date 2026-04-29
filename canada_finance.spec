# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for CanadaFinance
# Build with: pyinstaller canada_finance.spec

import os

a = Analysis(
    ['app.py'],
    pathex=[],
    datas=[
        ('canada_finance/templates', 'canada_finance/templates'),
        ('canada_finance/static', 'canada_finance/static'),
        ('banks', 'banks'),
        ('rules', 'rules'),
    ],
    hiddenimports=['canada_finance'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CanadaFinance',
    debug=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
