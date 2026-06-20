# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: FastAPI サーバーを単体実行ファイルにバンドルする
# ビルド: pyinstaller api-server.spec --distpath dist

a = Analysis(
    ['src/api/main.py'],
    pathex=['.'],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'src.api.routes.health',
        'src.api.routes.simulate',
        'src.api.routes.clients',
        'src.api.routes.comment',
        'src.api.routes.pdf',
        'src.db.sqlite_repository',
        'sqlalchemy.dialects.sqlite',
    ],
    datas=[
        ('scenario.yaml', '.'),
    ],
)
pyz = PYZ(a.pure)
# --onedir: 起動速度を優先（Electron インストーラーに含めるため単一 exe は不要）
# exclude_binaries=True で EXE をスタブ化し、バイナリ/データは COLLECT 側にまとめる。
# これを省くと EXE が dist/api-server（ファイル）を作り、COLLECT の dist/api-server
# （ディレクトリ）と衝突してビルドが失敗する。
exe = EXE(pyz, a.scripts, exclude_binaries=True, name='api-server', console=True)
coll = COLLECT(exe, a.binaries, a.datas, name='api-server')
