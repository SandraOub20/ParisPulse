"""A COMPLETER : Initialisation, chargement et gestion de tous les modèles (E2, Chronos-2, Google etc.)"""

from src.models.known import train

TEAM2_MODEL_RUN_ID = "e2-mlp-ctx-20260701-s0-9ce9"
class ModelManager:

    def __init__(self):
        self.models = {}

    def load_model(self, model_name):

        if model_name in self.models:
            return self.models[model_name]

        if model_name == "chronos-2":
            # Chargement local pour que l'import du package E3 ne requière pas
            # Chronos lorsque seul un autre modèle est utilisé.
            from chronos import Chronos2Pipeline

            model = Chronos2Pipeline.from_pretrained(
                "amazon/chronos-2",
                device_map="auto"
            )
        elif model_name == "google_TimesFM_2.5":
            # TODO : initialisation du modèle Google TimesFM 2.5
            model = None
        elif model_name == "team2":
            model = train.load_model(TEAM2_MODEL_RUN_ID) 

        else:
            raise ValueError(
                f"Modèle inconnu : {model_name}"
            )

        self.models[model_name] = model

        return model


manager = ModelManager()
