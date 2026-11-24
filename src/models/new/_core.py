"""A COMPLETER : Initialisation, chargement et gestion de tous les modèles (E2, Chronos-2, Google etc.)"""


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
            import timesfm

            model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
                "google/timesfm-2.5-200m-pytorch"
            )
            model.compile(
                timesfm.ForecastConfig(
                    max_context=1024,
                    max_horizon=256,
                    normalize_inputs=True,
                    use_continuous_quantile_head=True,
                    force_flip_invariance=True,
                    infer_is_positive=True,
                    fix_quantile_crossing=True,
                )
            )
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
