"""Configuración de pruebas.

La app calcula la ruta de la base al importarse (``expanduser("~")`` y ``APPDATA``), así que aquí se
redirigen esas variables a una carpeta temporal ANTES de importar ``mi_kinder_web``. Así las pruebas
nunca tocan la base real del colegio.
"""
import atexit
import os
import shutil
import sqlite3
import tempfile
from datetime import date, timedelta

import bcrypt
import pytest

_TMP_HOME = tempfile.mkdtemp(prefix="mikinder_pruebas_")
# Al terminar se borra la carpeta temporal (base sembrada y secreto de sesión de prueba).
atexit.register(shutil.rmtree, _TMP_HOME, ignore_errors=True)
os.environ["USERPROFILE"] = _TMP_HOME
os.environ["HOME"] = _TMP_HOME
os.environ["APPDATA"] = os.path.join(_TMP_HOME, "AppData", "Roaming")

from mi_kinder_web import config as web_config

assert os.path.abspath(web_config.DB_PATH).startswith(os.path.abspath(_TMP_HOME)), (
    "La base de pruebas no quedó en la carpeta temporal; se detienen las pruebas para no tocar la real."
)

PASSWORD = "prueba123"


def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=4)).decode()


def _sembrar(db_path):
    """Dos maestras con un grupo cada una, un grupo sin maestra y un alumno por grupo."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    hoy = date.today()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO school_years (name, start_date, end_date, is_active) VALUES (?, ?, ?, 1)",
        ("Ciclo Prueba", (hoy - timedelta(days=60)).isoformat(), (hoy + timedelta(days=200)).isoformat()),
    )
    year_id = cur.lastrowid
    conn.execute("UPDATE school_info SET current_year_id = ? WHERE id = 1", (year_id,))
    cur.execute(
        "INSERT INTO periods (school_year_id, name, start_date, end_date, sort_order) VALUES (?, ?, ?, ?, 1)",
        (year_id, "Periodo Uno", (hoy - timedelta(days=60)).isoformat(), (hoy + timedelta(days=60)).isoformat()),
    )
    period_id = cur.lastrowid
    cur.execute(
        "INSERT INTO evaluation_areas (school_year_id, name, sort_order) VALUES (?, ?, 1)",
        (year_id, "Lenguaje Prueba"),
    )
    area_id = cur.lastrowid

    ids = {"year": year_id, "period": period_id, "area": area_id}
    for clave, usuario, nombre in (("maestra_a", "maestra.a", "Maestra Alfa"),
                                   ("maestra_b", "maestra.b", "Maestra Beta"),
                                   ("maestra_sin", "maestra.sin", "Maestra Singrupo")):
        cur.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, 'maestra')",
            (usuario, _hash(PASSWORD), nombre),
        )
        ids[clave] = cur.lastrowid

    for clave, nombre in (("grupo_a", "Grupo Alfa"), ("grupo_b", "Grupo Beta"), ("grupo_c", "Grupo Gamma")):
        cur.execute(
            "INSERT INTO groups_ (school_year_id, name, grade_level, capacity) VALUES (?, ?, '2', 20)",
            (year_id, nombre),
        )
        ids[clave] = cur.lastrowid
    conn.execute("INSERT INTO user_group_assignments (user_id, group_id) VALUES (?, ?)",
                 (ids["maestra_a"], ids["grupo_a"]))
    conn.execute("INSERT INTO user_group_assignments (user_id, group_id) VALUES (?, ?)",
                 (ids["maestra_b"], ids["grupo_b"]))

    cumple = (hoy + timedelta(days=5)).replace(year=2021).isoformat()
    for clave, grupo, nombre, apellido in (("alumno_a", "grupo_a", "Anaclara", "Alfaro"),
                                           ("alumno_b", "grupo_b", "Brunoberto", "Betancourt"),
                                           ("alumno_c", "grupo_c", "Ceciliana", "Gamboa")):
        cur.execute(
            """INSERT INTO students (group_id, first_name, last_name, birth_date, gender)
               VALUES (?, ?, ?, ?, 'F')""",
            (ids[grupo], nombre, apellido, cumple),
        )
        ids[clave] = cur.lastrowid
        conn.execute(
            "INSERT INTO attendance_records (student_id, date, status) VALUES (?, ?, 'absent')",
            (ids[clave], hoy.isoformat()),
        )

    scale = conn.execute("SELECT id FROM grading_scales WHERE is_default = 1").fetchone()
    level = conn.execute(
        "SELECT id, numeric_value FROM grading_scale_levels WHERE grading_scale_id = ? ORDER BY sort_order",
        (scale["id"],),
    ).fetchone()
    ids["scale"] = scale["id"]
    ids["level"] = level["id"]
    for clave in ("alumno_a", "alumno_b"):
        conn.execute(
            """INSERT INTO evaluations (student_id, evaluation_area_id, period_id, grading_scale_id,
                                        grade_level_id, numeric_value)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ids[clave], area_id, period_id, scale["id"], level["id"], level["numeric_value"]),
        )
    conn.execute(
        "INSERT INTO student_observations (student_id, period_id, content, created_by) VALUES (?, ?, ?, ?)",
        (ids["alumno_b"], period_id, "Observacion privada de Beta", ids["maestra_b"]),
    )
    conn.commit()
    conn.close()
    return ids


@pytest.fixture
def entorno():
    """App nueva sobre una base temporal recién sembrada, para cada prueba."""
    for sufijo in ("", "-wal", "-shm"):
        ruta = web_config.DB_PATH + sufijo
        if os.path.exists(ruta):
            os.remove(ruta)
    from mi_kinder_web.app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    ids = _sembrar(web_config.DB_PATH)
    return app, ids


def entrar(app, usuario, password=PASSWORD):
    cliente = app.test_client()
    resp = cliente.post("/login", data={"username": usuario, "password": password})
    assert resp.status_code == 302, f"no pudo entrar {usuario}"
    return cliente


@pytest.fixture
def directora(entorno):
    app, ids = entorno
    return entrar(app, "directora", "admin123"), ids


@pytest.fixture
def maestra_a(entorno):
    app, ids = entorno
    return entrar(app, "maestra.a"), ids


@pytest.fixture
def maestra_sin(entorno):
    app, ids = entorno
    return entrar(app, "maestra.sin"), ids


def consulta(sql, params=()):
    conn = sqlite3.connect(web_config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()
