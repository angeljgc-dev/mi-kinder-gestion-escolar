"""Criterios de aceptación: cada maestra trabaja solo con sus grupos asignados.

C1  La directora ve y opera todos los grupos (no cambia nada para ella).
C2  En las listas de grupos de cada pantalla, la maestra solo ve sus grupos asignados.
C3  Si la maestra pide un grupo ajeno (páginas o PDF/Excel), se le niega (redirección con aviso)
    y la respuesta no contiene datos de ese grupo. En las rutas JSON recibe 403.
C4  Si la maestra envía datos para un grupo o alumno ajeno (asistencia, evaluaciones,
    observaciones), no se escribe nada.
C5  Boleta, PDF y gráfica de progreso de un alumno ajeno: negados.
C6  Traspasar alumnos de grupo: solo la directora (igual que dar de baja).
C7  Al editar a un alumno, la maestra no puede cambiarlo de grupo (ni a uno ajeno ni entre los
    suyos): los cambios de grupo son traspasos y quedan solo para la directora, con su historial.
C8  El panel de la maestra resume solo sus grupos (alumnos, grupos, inasistencias, cumpleaños).
C9  Una maestra sin grupos asignados no ve alumnos de nadie y nada truena.
"""
import pytest
from conftest import consulta, entrar

AJENOS = ("Grupo Beta", "Grupo Gamma", "Brunoberto", "Ceciliana", "Observacion privada de Beta")


def texto(resp):
    return resp.get_data(as_text=True)


def sin_datos_ajenos(resp):
    cuerpo = texto(resp)
    return [a for a in AJENOS if a in cuerpo]


# ---------- C1: la directora no cambia ----------

PAGINAS_DIRECTORA = [
    "/", "/groups", "/students", "/attendance", "/attendance/report", "/evaluations",
    "/reports", "/charts", "/socioemocional",
]


@pytest.mark.parametrize("ruta", PAGINAS_DIRECTORA)
def test_c1_directora_ve_todos_los_grupos(directora, ruta):
    cliente, _ = directora
    resp = cliente.get(ruta)
    assert resp.status_code == 200
    cuerpo = texto(resp)
    if ruta not in ("/",):
        assert "Grupo Beta" in cuerpo and "Grupo Alfa" in cuerpo


def test_c1_directora_abre_grupo_y_reportes_de_cualquiera(directora):
    cliente, ids = directora
    assert cliente.get(f"/groups/{ids['grupo_b']}").status_code == 200
    assert cliente.get(f"/reports/group/{ids['grupo_b']}").status_code == 200
    assert cliente.get(f"/reports/individual/{ids['alumno_b']}").status_code == 200
    assert cliente.get(f"/reports/individual/{ids['alumno_b']}/pdf").status_code == 200
    assert cliente.get(f"/reports/group/{ids['grupo_b']}/pdf").status_code == 200
    r = cliente.get(f"/api/students-list?group_id={ids['grupo_b']}")
    assert r.status_code == 200 and r.get_json()[0]["name"].startswith("Brunoberto")
    r = cliente.get(f"/charts/student-progress?student_id={ids['alumno_b']}")
    assert r.status_code == 200


def test_c1_directora_guarda_asistencia_de_cualquier_grupo(directora):
    cliente, ids = directora
    cliente.post("/attendance/save", data={"group_id": ids["grupo_b"], "date": "2026-01-15",
                                           f"status_{ids['alumno_b']}": "late"})
    filas = consulta("SELECT status FROM attendance_records WHERE student_id = ? AND date = '2026-01-15'",
                     (ids["alumno_b"],))
    assert [f["status"] for f in filas] == ["late"]


def test_c1_directora_puede_traspasar(directora):
    cliente, ids = directora
    cliente.post(f"/students/{ids['alumno_a']}/transfer", data={"to_group_id": ids["grupo_b"]})
    assert consulta("SELECT group_id FROM students WHERE id = ?", (ids["alumno_a"],))[0]["group_id"] == ids["grupo_b"]


# ---------- C2: listas filtradas ----------

@pytest.mark.parametrize("ruta", [
    "/groups", "/students", "/attendance", "/attendance/report", "/evaluations",
    "/reports", "/charts", "/socioemocional",
])
def test_c2_maestra_solo_ve_sus_grupos_en_listas(maestra_a, ruta):
    cliente, _ = maestra_a
    resp = cliente.get(ruta)
    assert resp.status_code == 200
    assert "Grupo Alfa" in texto(resp)
    assert sin_datos_ajenos(resp) == []


# ---------- C3: grupo ajeno negado ----------

def rutas_grupo_ajeno(ids):
    g = ids["grupo_b"]
    p = ids["period"]
    return [
        f"/groups/{g}",
        f"/attendance?group_id={g}",
        f"/attendance/report?group_id={g}&start_date=2000-01-01&end_date=2100-01-01",
        f"/evaluations?group_id={g}&period_id={p}",
        f"/socioemocional?group_id={g}",
        f"/students?group_id={g}",
        f"/reports/group/{g}",
        f"/reports/group/{g}/pdf",
        f"/exports/students-excel?group_id={g}",
        f"/exports/attendance-excel?group_id={g}&start_date=2000-01-01&end_date=2100-01-01",
    ]


def test_c3_maestra_no_abre_grupo_ajeno(maestra_a):
    cliente, ids = maestra_a
    for ruta in rutas_grupo_ajeno(ids):
        resp = cliente.get(ruta)
        assert resp.status_code in (302, 403), f"{ruta} respondió {resp.status_code}"
        assert sin_datos_ajenos(resp) == [], f"{ruta} filtró datos ajenos"
        assert resp.mimetype not in ("application/pdf",
                                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), ruta


def test_c3_maestra_si_abre_su_grupo(maestra_a):
    cliente, ids = maestra_a
    g = ids["grupo_a"]
    assert cliente.get(f"/groups/{g}").status_code == 200
    assert "Anaclara" in texto(cliente.get(f"/attendance?group_id={g}"))
    assert cliente.get(f"/reports/group/{g}").status_code == 200
    assert cliente.get(f"/reports/group/{g}/pdf").status_code == 200
    assert cliente.get(f"/exports/students-excel?group_id={g}").status_code == 200


@pytest.mark.parametrize("ruta", [
    "/charts/group-averages?group_id={g}&period_id={p}",
    "/charts/group-distribution?group_id={g}&period_id={p}",
    "/charts/attendance-chart?group_id={g}&start_date=2000-01-01&end_date=2100-01-01",
    "/api/students-list?group_id={g}",
])
def test_c3_maestra_recibe_403_en_json_de_grupo_ajeno(maestra_a, ruta):
    cliente, ids = maestra_a
    resp = cliente.get(ruta.format(g=ids["grupo_b"], p=ids["period"]))
    assert resp.status_code == 403
    assert sin_datos_ajenos(resp) == []


def test_c3_excel_sin_grupo_solo_trae_sus_alumnos(maestra_a, tmp_path):
    from openpyxl import load_workbook

    cliente, _ = maestra_a
    resp = cliente.get("/exports/students-excel")
    assert resp.status_code == 200
    archivo = tmp_path / "alumnos.xlsx"
    archivo.write_bytes(resp.data)
    hoja = load_workbook(archivo).active
    nombres = [hoja.cell(row=r, column=4).value for r in range(2, hoja.max_row + 1)]
    assert nombres == ["Anaclara"]


# ---------- C4: escrituras sobre ajenos ----------

def test_c4_maestra_no_guarda_asistencia_de_grupo_ajeno(maestra_a):
    cliente, ids = maestra_a
    cliente.post("/attendance/save", data={"group_id": ids["grupo_b"], "date": "2026-01-15",
                                           f"status_{ids['alumno_b']}": "late"})
    assert consulta("SELECT * FROM attendance_records WHERE student_id = ? AND date = '2026-01-15'",
                    (ids["alumno_b"],)) == []


def test_c4_maestra_no_guarda_evaluaciones_de_grupo_ajeno(maestra_a):
    cliente, ids = maestra_a
    antes = consulta("SELECT grade_level_id, observations FROM evaluations WHERE student_id = ?", (ids["alumno_b"],))
    otro_nivel = consulta("SELECT id FROM grading_scale_levels WHERE grading_scale_id = ? ORDER BY sort_order DESC",
                          (ids["scale"],))[0]["id"]
    cliente.post("/evaluations/save", data={
        "group_id": ids["grupo_b"], "period_id": ids["period"],
        f"grade_{ids['alumno_b']}_{ids['area']}": otro_nivel,
        f"obs_{ids['alumno_b']}_{ids['area']}": "cambio indebido",
    })
    despues = consulta("SELECT grade_level_id, observations FROM evaluations WHERE student_id = ?", (ids["alumno_b"],))
    assert [tuple(f) for f in despues] == [tuple(f) for f in antes]


def test_c4_maestra_no_agrega_observacion_a_alumno_ajeno(maestra_a):
    cliente, ids = maestra_a
    cliente.post("/socioemocional/add", data={"student_id": ids["alumno_b"], "period_id": ids["period"],
                                              "content": "nota indebida", "group_id": ids["grupo_b"]})
    assert consulta("SELECT * FROM student_observations WHERE content = 'nota indebida'") == []


def test_c4_maestra_si_guarda_en_su_grupo(maestra_a):
    cliente, ids = maestra_a
    cliente.post("/attendance/save", data={"group_id": ids["grupo_a"], "date": "2026-01-15",
                                           f"status_{ids['alumno_a']}": "late"})
    cliente.post("/socioemocional/add", data={"student_id": ids["alumno_a"], "period_id": ids["period"],
                                              "content": "nota propia", "group_id": ids["grupo_a"]})
    assert len(consulta("SELECT * FROM attendance_records WHERE student_id = ? AND date = '2026-01-15'",
                        (ids["alumno_a"],))) == 1
    assert len(consulta("SELECT * FROM student_observations WHERE content = 'nota propia'")) == 1


# ---------- C5: alumno ajeno ----------

def test_c5_maestra_no_ve_boleta_ni_progreso_de_alumno_ajeno(maestra_a):
    cliente, ids = maestra_a
    s = ids["alumno_b"]
    for ruta in (f"/reports/individual/{s}", f"/reports/individual/{s}/pdf", f"/students/{s}"):
        resp = cliente.get(ruta)
        assert resp.status_code in (302, 403), ruta
        assert resp.mimetype != "application/pdf", ruta
        assert sin_datos_ajenos(resp) == [], ruta
    assert cliente.get(f"/charts/student-progress?student_id={s}").status_code == 403


def test_c5_maestra_si_ve_boleta_de_su_alumno(maestra_a):
    cliente, ids = maestra_a
    s = ids["alumno_a"]
    assert cliente.get(f"/reports/individual/{s}").status_code == 200
    assert cliente.get(f"/reports/individual/{s}/pdf").mimetype == "application/pdf"
    assert cliente.get(f"/charts/student-progress?student_id={s}").status_code == 200


# ---------- C6 y C7: traspaso y edición ----------

def test_c6_maestra_no_puede_traspasar(maestra_a):
    cliente, ids = maestra_a
    cliente.post(f"/students/{ids['alumno_a']}/transfer", data={"to_group_id": ids["grupo_b"]})
    assert consulta("SELECT group_id FROM students WHERE id = ?", (ids["alumno_a"],))[0]["group_id"] == ids["grupo_a"]
    assert consulta("SELECT * FROM student_transfers") == []


def test_c7_maestra_no_mueve_a_grupo_ajeno_al_editar(maestra_a):
    cliente, ids = maestra_a
    cliente.post(f"/students/{ids['alumno_a']}/edit", data={
        "first_name": "Anaclara", "last_name": "Alfaro", "group_id": ids["grupo_b"],
    })
    assert consulta("SELECT group_id FROM students WHERE id = ?", (ids["alumno_a"],))[0]["group_id"] == ids["grupo_a"]


def test_c7_maestra_si_edita_a_su_alumno(maestra_a):
    cliente, ids = maestra_a
    cliente.post(f"/students/{ids['alumno_a']}/edit", data={
        "first_name": "Anaclara", "last_name": "Alfaro Editada", "group_id": ids["grupo_a"],
    })
    assert consulta("SELECT last_name FROM students WHERE id = ?", (ids["alumno_a"],))[0]["last_name"] == "Alfaro Editada"


# ---------- C8: panel ----------

def test_c8_panel_de_maestra_resume_solo_sus_grupos(maestra_a):
    cliente, _ = maestra_a
    resp = cliente.get("/")
    assert resp.status_code == 200
    assert "Anaclara" in texto(resp)
    assert sin_datos_ajenos(resp) == []


def test_c8_panel_de_directora_resume_todo(directora):
    cliente, _ = directora
    cuerpo = texto(cliente.get("/"))
    assert "Brunoberto" in cuerpo and "Anaclara" in cuerpo


# ---------- C9: maestra sin grupos ----------

@pytest.mark.parametrize("ruta", PAGINAS_DIRECTORA)
def test_c9_maestra_sin_grupos_no_ve_nada_ajeno(maestra_sin, ruta):
    cliente, _ = maestra_sin
    resp = cliente.get(ruta)
    assert resp.status_code == 200
    cuerpo = texto(resp)
    assert "Anaclara" not in cuerpo and "Grupo Alfa" not in cuerpo
    assert sin_datos_ajenos(resp) == []


# ---------- Casos adicionales de la revisión independiente ----------

def test_c3_la_maestra_ve_el_aviso_al_ser_negada(maestra_a):
    cliente, ids = maestra_a
    resp = cliente.get(f"/groups/{ids['grupo_b']}", follow_redirects=True)
    assert resp.status_code == 200
    assert "No tienes permiso para ver ese grupo o alumno." in texto(resp)
    assert sin_datos_ajenos(resp) == []


def test_c2_maestra_con_dos_grupos_ve_ambos_y_ninguno_ajeno(entorno):
    app, ids = entorno
    consulta_escritura(
        "INSERT INTO user_group_assignments (user_id, group_id) VALUES (?, ?)",
        (ids["maestra_a"], ids["grupo_c"]),
    )
    cliente = entrar(app, "maestra.a")
    for ruta in ("/", "/groups", "/students", "/attendance", "/evaluations", "/reports", "/charts",
                 "/socioemocional"):
        cuerpo = texto(cliente.get(ruta))
        assert "Grupo Beta" not in cuerpo and "Brunoberto" not in cuerpo, ruta
        if ruta != "/":
            assert "Grupo Alfa" in cuerpo and "Grupo Gamma" in cuerpo, ruta
    assert "Ceciliana" in texto(cliente.get(f"/attendance?group_id={ids['grupo_c']}"))


def test_c7_maestra_con_dos_grupos_no_cambia_de_grupo_al_editar(entorno):
    app, ids = entorno
    consulta_escritura(
        "INSERT INTO user_group_assignments (user_id, group_id) VALUES (?, ?)",
        (ids["maestra_a"], ids["grupo_c"]),
    )
    cliente = entrar(app, "maestra.a")
    cliente.post(f"/students/{ids['alumno_a']}/edit", data={
        "first_name": "Anaclara", "last_name": "Alfaro", "group_id": ids["grupo_c"],
    })
    assert consulta("SELECT group_id FROM students WHERE id = ?", (ids["alumno_a"],))[0]["group_id"] == ids["grupo_a"]


def consulta_escritura(sql, params=()):
    import sqlite3

    from mi_kinder_web import config as web_config

    conn = sqlite3.connect(web_config.DB_PATH)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()
