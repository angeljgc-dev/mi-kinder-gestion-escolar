# Verificacion completa de Mi Kinder: lint + pruebas.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File verify.ps1
# Las pruebas usan una base temporal; nunca tocan la base real del colegio.
$env:PYTHONUTF8 = '1'
Set-Location $PSScriptRoot

# Errores reales en todo el proyecto: sintaxis y nombres no definidos.
python -m ruff check --select E9,F63,F7,F82 mi_kinder mi_kinder_web tests run_web.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Reglas completas en el codigo nuevo de permisos y en las pruebas.
python -m ruff check mi_kinder_web/permissions.py tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest -q -p no:cacheprovider tests
exit $LASTEXITCODE
