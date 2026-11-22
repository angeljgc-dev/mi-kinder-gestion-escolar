"""Criterios de aceptación: los textos visibles de la app llevan acentos.

A1  La pantalla de inicio de sesión dice "Iniciar Sesión", "Contraseña", "Mantener sesión activa",
    "Centro de Atención Psicopedagógica Infantil", "Matías Romero, Oaxaca" y
    "Educación con valores", sin las versiones sin acento.
A2  El menú dice "Gráficas" y "Cerrar Sesión" (y su texto alternativo "Cerrar sesión").
A3  Al pedir una página sin entrar, el aviso dice "Inicia sesión para continuar."
A4  No cambia nada más: el nombre "Colegio CAPI" sigue visible.
"""
from conftest import entrar


def texto(resp):
    return resp.get_data(as_text=True)


def test_a1_login_con_acentos(entorno):
    app, _ = entorno
    cuerpo = texto(app.test_client().get("/login"))
    for bien in ("Iniciar Sesión", "Contraseña", "Mantener sesión activa",
                 "Centro de Atención Psicopedagógica Infantil", "Matías Romero, Oaxaca",
                 "Educación con valores"):
        assert bien in cuerpo, bien
    for mal in ("Iniciar Sesion", "Contrasena", "sesion activa", "Atencion", "Psicopedagogica",
                "Matias", "Educacion"):
        assert mal not in cuerpo, mal


def test_a2_menu_con_acentos(directora):
    cliente, _ = directora
    cuerpo = texto(cliente.get("/", follow_redirects=True))
    assert "Gráficas" in cuerpo
    assert "Cerrar Sesión" in cuerpo
    assert 'title="Cerrar sesión"' in cuerpo
    for mal in ("Graficas", "Cerrar Sesion", "Cerrar sesion"):
        assert mal not in cuerpo, mal


def test_a3_aviso_de_login_con_acento(entorno):
    app, _ = entorno
    cuerpo = texto(app.test_client().get("/students", follow_redirects=True))
    assert "Inicia sesión para continuar." in cuerpo
    assert "Inicia sesion" not in cuerpo


def test_a4_nombre_del_colegio_sigue(entorno):
    app, _ = entorno
    assert "Colegio CAPI" in texto(app.test_client().get("/login"))


def test_a2_maestra_tambien(maestra_a):
    cliente, _ = maestra_a
    cuerpo = texto(cliente.get("/", follow_redirects=True))
    assert "Gráficas" in cuerpo and "Cerrar Sesión" in cuerpo


def test_entrar_sigue_funcionando(entorno):
    app, _ = entorno
    cliente = entrar(app, "maestra.a")
    assert cliente.get("/", follow_redirects=True).status_code == 200
