
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pwdlib import PasswordHash

from database import get_connection


# Charger les informations du fichier .env
load_dotenv()

SESSION_SECRET = os.getenv("SESSION_SECRET")

if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET est absent du fichier .env")


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False
)

password_hash = PasswordHash.recommended()

NA = 6.022e23


# PAGE DE CONNEXION
@app.get("/login")
def afficher_login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"erreur": None}
    )


# VERIFICATION DES IDENTIFIANTS
@app.post("/login")
def connexion(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE username = %s",
                (username.strip(),)
            )

            user = cursor.fetchone()

            if user is None:
                return templates.TemplateResponse(
                    request=request,
                    name="login.html",
                    context={"erreur": "Identifiants incorrects."}
                )

            if not user["is_active"] or user["login_attempt_used"]:
                return templates.TemplateResponse(
                    request=request,
                    name="login.html",
                    context={
                        "erreur": "Compte indisponible. Contactez l'administratrice."
                    }
                )

            correct = password_hash.verify(
                password,
                user["password_hash"]
            )

            if correct:
                request.session["username"] = user["username"]
                return RedirectResponse("/", status_code=303)

            cursor.execute(
                """
                UPDATE users
                SET login_attempt_used = TRUE, is_active = FALSE
                WHERE id = %s
                """,
                (user["id"],)
            )
            connection.commit()

            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={
                    "erreur": "Identifiants incorrects. Contactez l'administratrice."
                }
            )

    finally:
        connection.close()


# PAGE PRINCIPALE : CALCULATEUR
@app.get("/")
def accueil(request: Request):

    if "username" not in request.session:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


# CALCUL DE LA QUANTITE DE MATIERE
@app.post("/calculer")
def calculer(
    request: Request,
    methode: str = Form(...),
    masse: float | None = Form(None),
    masse_molaire: float | None = Form(None),
    concentration: float | None = Form(None),
    volume: float | None = Form(None),
    nombre_entites: float | None = Form(None)
):

    if "username" not in request.session:
        return RedirectResponse("/login", status_code=303)

    try:
        if methode == "masse":

            if masse is None or masse_molaire is None:
                raise ValueError("Veuillez remplir tous les champs.")

            if masse < 0 or masse_molaire <= 0:
                raise ValueError("Valeurs invalides.")

            n = masse / masse_molaire
            formule = "n = m / M"

        elif methode == "concentration":

            if concentration is None or volume is None:
                raise ValueError("Veuillez remplir tous les champs.")

            if concentration < 0 or volume < 0:
                raise ValueError("Valeurs invalides.")

            n = concentration * volume
            formule = "n = C × V"

        elif methode == "entites":

            if nombre_entites is None or nombre_entites < 0:
                raise ValueError("Valeur invalide.")

            n = nombre_entites / NA
            formule = "n = N / NA"

        else:
            raise ValueError("Méthode inconnue.")

        return templates.TemplateResponse(
            request=request,
            name="resultat.html",
            context={
                "resultat": n,
                "formule": formule,
                "erreur": None
            }
        )

    except ValueError as e:
        return templates.TemplateResponse(
            request=request,
            name="resultat.html",
            context={
                "resultat": None,
                "formule": None,
                "erreur": str(e)
            }
        )


# DECONNEXION
@app.get("/logout")
def deconnexion(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

# VERIFIER SI L'UTILISATEUR EST ADMINISTRATEUR
def verifier_admin(request: Request):
    username = request.session.get("username")

    if not username:
        return False

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT role FROM users WHERE username = %s",
                (username,)
            )
            user = cursor.fetchone()

            return user is not None and user["role"] == "admin"
    finally:
        connection.close()


# PAGE ADMINISTRATEUR
@app.get("/admin")
def page_admin(request: Request):

    if "username" not in request.session:
        return RedirectResponse("/login", status_code=303)

    if not verifier_admin(request):
        return RedirectResponse("/", status_code=303)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, role, is_active, login_attempt_used
                FROM users
                ORDER BY id
                """
            )
            utilisateurs = cursor.fetchall()

        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={"utilisateurs": utilisateurs}
        )
    finally:
        connection.close()


# CREER UN NOUVEL UTILISATEUR
@app.post("/admin/create-user")
def creer_utilisateur(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):

    if not verifier_admin(request):
        return RedirectResponse("/login", status_code=303)

    username = username.strip()

    if not username or len(password) < 8:
        return RedirectResponse("/admin?message=Mot+de+passe+minimum+8+caracteres", status_code=303)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users
                (username, password_hash, login_attempt_used, is_active, role)
                VALUES (%s, %s, FALSE, TRUE, 'user')
                """,
                (username, password_hash.hash(password))
            )

        connection.commit()

    except Exception:
        connection.rollback()
        return RedirectResponse("/admin?message=Erreur+ou+nom+deja+utilise", status_code=303)

    finally:
        connection.close()

    return RedirectResponse("/admin?message=Utilisateur+cree", status_code=303)


# REACTIVER UN COMPTE BLOQUE
@app.post("/admin/reactiver/{user_id}")
def reactiver_utilisateur(
    request: Request,
    user_id: int
):

    if not verifier_admin(request):
        return RedirectResponse("/login", status_code=303)

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET is_active = TRUE, login_attempt_used = FALSE
                WHERE id = %s AND role = 'user'
                """,
                (user_id,)
            )

        connection.commit()

    finally:
        connection.close()

    return RedirectResponse("/admin", status_code=303)
