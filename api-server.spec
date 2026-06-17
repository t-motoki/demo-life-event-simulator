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
exe = EXE(pyz, a.scripts, name='api-server', console=True)
# --onedir: 起動速度を優先（Electron インストーラーに含めるため単一 exe は不要）
coll = COLLECT(exe, a.binaries, a.datas, name='api-server')
