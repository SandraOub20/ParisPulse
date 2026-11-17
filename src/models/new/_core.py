"""A COMPLETER : Initialisation, chargement et gestion de tous les modèles (E2, Chronos-2, Google etc.)"""
from chronos import Chronos2Pipeline


class ModelManager:

    def __init__(self):
        self.models = {}

    def load_model(self, model_name):

        if model_name in self.models:
            return self.models[model_name]

        if model_name == "chronos-2":
            model = Chronos2Pipeline.from_pretrained(
                "amazon/chronos-2",
                device_map="auto"
            )
        elif model_name == "google_TimesFM_2.5":
            # TODO : initialisation du modèle Google TimesFM 2.5
            model = None
        elif model_name == "team2":
            # TODO : initialisation du modèle E2
            model = None

        else:
            raise ValueError(
                f"Modèle inconnu : {model_name}"
            )

        self.models[model_name] = model

        return model


manager = ModelManager()
