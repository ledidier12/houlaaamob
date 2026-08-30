from flask import Flask, request, render_template
from flask_socketio import SocketIO
import time


# ==================================================
# APPLICATION
# ==================================================

app = Flask(__name__)

socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)


# ==================================================
# ÉTAT DE LA COURSE
# ==================================================

race_start_time = None
race_paused = False
elapsed_time = 0.0


# ==================================================
# MODE
#
# 1 = Qualifications
# 2 = Course
# 3 = Endurance
# ==================================================

resultat_mode = 0


# ==================================================
# RÉSULTATS DE LA COURSE PRÉCÉDENTE
#
# Exemple :
#
# {
#     "02": 7,
#     "26": 6,
#     "25": 6
# }
# ==================================================

previous_results = {}


# ==================================================
# DERNIÈRES DONNÉES
# ==================================================

last_data = {
    "classement": []
}


# ==================================================
# PAGE
# ==================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ==================================================
# TEMPS DE COURSE
# ==================================================

def get_race_time():

    global race_start_time
    global race_paused
    global elapsed_time


    # Course arrêtée
    if race_start_time is None:

        return elapsed_time


    # Course en pause
    if race_paused:

        return elapsed_time


    # Course en cours
    return (
        elapsed_time
        +
        (
            time.time()
            -
            race_start_time
        )
    )


# ==================================================
# ENVOI CHRONO
# ==================================================

def send_chrono():

    chrono = get_race_time()


    socketio.emit(
        "chrono_update",
        {
            "time": chrono,

            "running":
                race_start_time is not None
                and not race_paused,

            "paused":
                race_paused
        }
    )


# ==================================================
# BOUCLE CHRONO
# ==================================================

def chrono_loop():

    while True:

        socketio.sleep(0.1)

        if race_start_time is not None:

            send_chrono()


# ==================================================
# CONSTRUCTION CLASSEMENT
# ==================================================

def construire_classement(data):

    global resultat_mode
    global previous_results


    pilotes = data.get(
        "pilots",
        []
    )


    pilots_place = data.get(
        "pilots_place",
        {}
    )


    laps = data.get(
        "pilots_numberOfLaps",
        {}
    )


    bestlaps = data.get(
        "pilot_bestlap",
        {}
    )


    classement = []


    # ==================================================
    # CONSTRUCTION DES DONNÉES
    # ==================================================

    for index, pilote in enumerate(pilotes):


        # ----------------------------------------------
        # TOURS EN COURS
        # ----------------------------------------------

        tours = laps.get(
            pilote,
            0
        )


        try:

            tours = int(tours)

        except (
            ValueError,
            TypeError
        ):

            tours = 0


        # ----------------------------------------------
        # MEILLEUR TOUR
        # ----------------------------------------------

        bestlap_data = bestlaps.get(
            pilote,
            [0, 0]
        )


        if isinstance(
            bestlap_data,
            list
        ):

            if len(bestlap_data) > 0:

                bestlap = (
                    bestlap_data[0]
                )

            else:

                bestlap = 0

        else:

            bestlap = bestlap_data


        try:

            bestlap = float(
                bestlap
            )

        except (
            ValueError,
            TypeError
        ):

            bestlap = 0


        # ----------------------------------------------
        # PLACE FOURNIE PAR CHRONOPY
        # ----------------------------------------------

        place_chronopy = pilots_place.get(
            pilote,
            999999
        )


        try:

            place_chronopy = int(
                place_chronopy
            )

        except (
            ValueError,
            TypeError
        ):

            place_chronopy = 999999


        # ----------------------------------------------
        # TOURS PRÉCÉDENTS
        # ----------------------------------------------

        tours_precedents = previous_results.get(
            pilote,
            0
        )


        try:

            tours_precedents = int(
                tours_precedents
            )

        except (
            ValueError,
            TypeError
        ):

            tours_precedents = 0


        # ----------------------------------------------
        # TOURS TOTAL
        # ----------------------------------------------

        tours_total = (
            tours_precedents
            +
            tours
        )


        classement.append(
            {
                "pilote": pilote,

                "tours": tours,

                "bestlap": bestlap,

                "place_chronopy":
                    place_chronopy,

                "tours_precedents":
                    tours_precedents,

                "tours_total":
                    tours_total,

                # Permet de conserver
                # l'ordre original
                "_index":
                    index
            }
        )


    # ==================================================
    # TRI
    # ==================================================

    if resultat_mode == 1:

        # ----------------------------------------------
        # QUALIFICATIONS
        # ----------------------------------------------
        # Meilleur tour uniquement

        classement.sort(
            key=lambda x: (
                x["bestlap"]
                if x["bestlap"] > 0
                else float("inf")
            )
        )


    elif resultat_mode == 2:

        # ----------------------------------------------
        # COURSE
        # ----------------------------------------------
        #
        # On utilise UNIQUEMENT la place fournie
        # par Chronopy.
        #
        # Chronopy a déjà calculé le classement.
        #

        classement.sort(
            key=lambda x:
                x["place_chronopy"]
        )


    elif resultat_mode == 3:

        # ----------------------------------------------
        # ENDURANCE
        # ----------------------------------------------
        #
        # Tours total =
        #
        # tours de la course précédente
        # +
        # tours de la course actuelle
        #
        # Plus grand nombre de tours total
        # = meilleure position.
        #
        # En cas d'égalité, on conserve l'ordre
        # fourni par Chronopy.
        #

        classement.sort(
            key=lambda x: (
                -x["tours_total"],
                x["_index"]
            )
        )


    else:

        # ----------------------------------------------
        # MODE INCONNU
        # ----------------------------------------------

        classement.sort(
            key=lambda x:
                x["place_chronopy"]
        )


    # ==================================================
    # ATTRIBUTION DES PLACES
    # ==================================================

    for i, row in enumerate(
        classement
    ):

        row["place"] = i + 1


    # ==================================================
    # SUPPRESSION DONNÉE INTERNE
    # ==================================================

    for row in classement:

        del row["_index"]


    return classement


# ==================================================
# RÉCEPTION DES ÉVÉNEMENTS
# ==================================================

@app.route(
    "/event",
    methods=["POST"]
)
def event():

    global race_start_time
    global race_paused
    global elapsed_time

    global resultat_mode
    global previous_results


    data = request.get_json(
        silent=True
    ) or {}


    print(
        "EVENT REÇU :",
        data
    )


    event_type = data.get(
        "event"
    )


    # ==================================================
    # CHANGEMENT DE MODE
    # ==================================================

    if event_type == "mode":

        resultat_mode = data.get(
            "resultat_mode",
            0
        )


        try:

            resultat_mode = int(
                resultat_mode
            )

        except (
            ValueError,
            TypeError
        ):

            resultat_mode = 0


        print(
            "🎛️ MODE :",
            resultat_mode
        )


        # ----------------------------------------------
        # INFORMER LE HTML
        # ----------------------------------------------

        socketio.emit(
            "mode_update",
            {
                "mode":
                    resultat_mode
            }
        )


        # ----------------------------------------------
        # Si on possède déjà des données,
        # recalculer le classement
        # ----------------------------------------------

        if last_data["classement"]:

            # On ne peut pas reconstruire ici
            # à partir du classement déjà transformé.
            #
            # Le prochain update reconstruira
            # correctement le classement.


            pass


        return {
            "status": "ok"
        }


    # ==================================================
    # RÉSULTATS PRÉCÉDENTS
    # ==================================================

    if event_type == "previous_results":

        previous_results = data.get(
            "previous_results",
            {}
        )


        # Sécurisation des valeurs

        if not isinstance(
            previous_results,
            dict
        ):

            previous_results = {}


        print(
            "📋 RÉSULTATS PRÉCÉDENTS :",
            previous_results
        )


        # ----------------------------------------------
        # Informer le navigateur
        # ----------------------------------------------

        socketio.emit(
            "previous_results_update",
            previous_results
        )


        return {
            "status": "ok"
        }


    # ==================================================
    # UPDATE
    # ==================================================

    if event_type == "update":

        classement = construire_classement(
            data
        )


        last_data["classement"] = classement


        print(
            "📊 CLASSEMENT :",
            classement
        )


        socketio.emit(
            "classement_update",
            classement
        )


        return {
            "status": "ok"
        }


    # ==================================================
    # COURSE DÉMARRÉE
    # ==================================================

    if event_type == "race_started":

        race_start_time = time.time()

        race_paused = False

        elapsed_time = 0.0


        print(
            "🏁 COURSE DÉMARRÉE"
        )


        send_chrono()


        return {
            "status": "ok"
        }


    # ==================================================
    # COURSE EN PAUSE
    # ==================================================

    if event_type == "race_paused":

        if (
            race_start_time is not None
            and not race_paused
        ):


            elapsed_time += (
                time.time()
                -
                race_start_time
            )


            race_paused = True

            race_start_time = None


            print(
                "⏸️ COURSE EN PAUSE"
            )


            print(
                "Temps mémorisé :",
                elapsed_time
            )


            send_chrono()


        return {
            "status": "ok"
        }


    # ==================================================
    # COURSE REPRISE
    # ==================================================

    if event_type == "race_resumed":

        if race_paused:

            race_start_time = time.time()

            race_paused = False


            print(
                "▶️ COURSE REPRISE"
            )


            print(
                "Temps mémorisé :",
                elapsed_time
            )


            send_chrono()


        else:

            print(
                "⚠️ Reprise demandée "
                "mais la course n'est pas en pause"
            )


        return {
            "status": "ok"
        }


    # ==================================================
    # RESET
    # ==================================================

    if event_type == "race_reset":

        race_start_time = None

        race_paused = False

        elapsed_time = 0.0


        print(
            "🔄 COURSE RESET"
        )


        socketio.emit(
            "chrono_update",
            {
                "time": 0,

                "running": False,

                "paused": False
            }
        )


        socketio.emit(
            "classement_update",
            []
        )


        return {
            "status": "ok"
        }


    # ==================================================
    # ÉVÉNEMENT INCONNU
    # ==================================================

    print(
        "⚠️ Événement inconnu :",
        event_type
    )


    return {
        "status": "ok"
    }


# ==================================================
# DÉMARRAGE
# ==================================================

if __name__ == "__main__":
    socketio.start_background_task(
        chrono_loop
    )
    socketio.run(app)

