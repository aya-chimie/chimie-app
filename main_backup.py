
from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()

templates = Jinja2Templates(directory="templates")

NA = 6.022e23


@app.get("/")
def accueil(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


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
