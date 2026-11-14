
from getpass import getpass

from pwdlib import PasswordHash

from database import get_connection

password_hash = PasswordHash.recommended()

username = input("Nom d'utilisateur : ").strip()
password = getpass("Mot de passe : ")
confirmation = getpass("Confirmer le mot de passe : ")

if not username or not password:
    print("Erreur : les champs sont obligatoires.")

elif password != confirmation:
    print("Erreur : les mots de passe ne correspondent pas.")

else:
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users
                (username, password_hash, login_attempt_used, is_active)
                VALUES (%s, %s, FALSE, TRUE)
                """,
                (username, password_hash.hash(password))
            )

        connection.commit()
        print("Utilisateur créé avec succès !")

    except Exception as e:
        connection.rollback()
        print("Erreur lors de la création :", e)

    finally:
        connection.close()
