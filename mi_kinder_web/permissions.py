"""Permisos por grupo: la directora ve todo; cada maestra, solo sus grupos asignados."""
from flask import flash, jsonify, redirect, url_for

MSG_SIN_PERMISO = "No tienes permiso para ver ese grupo o alumno."


def is_directora(user):
    return user.role == "directora"


def user_group_ids(db, user_id):
    """Ids de los grupos asignados a este usuario."""
    rows = db.execute(
        "SELECT group_id FROM user_group_assignments WHERE user_id = ?", (user_id,)
    ).fetchall()
    return {r["group_id"] for r in rows}


def allowed_group_ids(db, user):
    """None = sin restricción (directora); si no, el conjunto de grupos permitidos."""
    if is_directora(user):
        return None
    return user_group_ids(db, user.id)


def can_access_group(db, user, group_id):
    allowed = allowed_group_ids(db, user)
    return allowed is None or group_id in allowed


def can_access_student(db, user, student_id):
    """Recibe el id del alumno; un alumno inexistente cuenta como sin acceso para la maestra."""
    if is_directora(user):
        return True
    row = db.execute("SELECT group_id FROM students WHERE id = ?", (student_id,)).fetchone()
    return bool(row) and row["group_id"] in user_group_ids(db, user.id)


def visible_groups(db, user, year_id):
    """Grupos activos del ciclo que este usuario puede ver, ordenados por nombre."""
    allowed = allowed_group_ids(db, user)
    if allowed is None:
        return db.execute(
            "SELECT * FROM groups_ WHERE school_year_id = ? AND is_active = 1 ORDER BY name",
            (year_id,),
        ).fetchall()
    if not allowed:
        return []
    ph = ",".join("?" * len(allowed))
    return db.execute(
        f"SELECT * FROM groups_ WHERE school_year_id = ? AND is_active = 1 AND id IN ({ph}) ORDER BY name",
        (year_id, *sorted(allowed)),
    ).fetchall()


def group_filter_sql(db, user, column):
    """Fragmento SQL (con parámetros) para limitar ``column`` a los grupos permitidos.

    Directora: ("", []). Maestra sin grupos: ("AND 0", []), que no devuelve filas.
    """
    allowed = allowed_group_ids(db, user)
    if allowed is None:
        return "", []
    if not allowed:
        return "AND 0", []
    ph = ",".join("?" * len(allowed))
    return f"AND {column} IN ({ph})", sorted(allowed)


def deny(endpoint, **values):
    """Respuesta para páginas: aviso y regreso a una vista segura."""
    flash(MSG_SIN_PERMISO, "error")
    return redirect(url_for(endpoint, **values))


def deny_json():
    return jsonify({"error": MSG_SIN_PERMISO}), 403
