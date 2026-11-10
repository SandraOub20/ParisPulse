# ParisPulse - Bibliographie initiale et sources

Préparation du **10 novembre 2026**. Les accès indiqués comme vérifiés ont été consultés pendant la mise à jour du plan. Les résumés d'articles donnent des pistes ; ils ne remplacent pas la lecture des sections méthodes et expériences avant le choix final. Aucune performance publiée ailleurs n'est transposée aux compteurs parisiens.

## 1. Références méthodologiques à examiner

| Référence | Intérêt pour ParisPulse | Travail à mener |
| --- | --- | --- |
| Hyndman & Athanasopoulos, [Forecasting: Principles and Practice, §5.10 - Time series cross-validation](https://otexts.com/fpp3/tscv.html) | Origines successives, entraînement limité au passé et précision selon horizon | E4 : formaliser coupures, purge des fenêtres et différences avec un découpage aléatoire |
| Salinas et al., [DeepAR: Probabilistic Forecasting with Autoregressive Recurrent Networks](https://arxiv.org/abs/1704.04110), prépublication 2017, révisée en 2019 | Réseau appris sur plusieurs séries apparentées ; intérêt d'un modèle partagé | E2/E3 : étudier les hypothèses et le coût, sans imposer de reproduire DeepAR |
| Zeng et al., [Are Transformers Effective for Time Series Forecasting?](https://arxiv.org/abs/2205.13504), prépublication 2022 | Nécessité de comparer à des solutions simples ; étude des modèles linéaires dans un autre contexte | E2 : construire des références solides ; ne pas présenter une couche linéaire seule comme l'expérience de deep learning obligatoire |
| Ansari et al., [Chronos: Learning the Language of Time Series](https://arxiv.org/abs/2403.07815), 2024 | Piste de modèle temporel préentraîné et de transfert | E3 : vérifier checkpoint, licence des poids, contexte requis, budget et corpus de préentraînement avant adoption |

Les titres et résumés des trois articles, ainsi que l'accès au chapitre méthodologique, ont été vérifiés. La proposition de petit MLP/GRU et de correcteur léger est une option d'ingénierie à justifier par les expériences ; elle ne constitue pas une implémentation annoncée de ces articles.

Un modèle de fondation n'est pas obligatoire. Une expérience d'apprentissage d'un réseau compact sur les seuls donneurs permet de satisfaire l'exigence DL tout en maîtrisant le corpus utilisé dans le projet.

## 2. Données publiques

- [Paris - Archives annuelles des comptages](https://opendata.paris.fr/explore/dataset/comptage-velo-historique-donnees-compteurs/information/) : pièces jointes 2016–2025 vérifiées ; distinguer compteur/heure et site/quart d'heure ; licence ODbL déclarée.
- [Paris - Flux récent](https://opendata.paris.fr/explore/dataset/comptage-velo-donnees-compteurs/information/) : accès API et bornes vérifiés le 10/11/2026 ; fenêtre glissante, doublons possibles avec archives et délai J−1 annoncé.
- [Paris - Inventaire des compteurs](https://opendata.paris.fr/explore/dataset/comptage-velo-compteurs/information/) : métadonnées accessibles ; les fiches actuelles ne garantissent pas la stabilité historique des lieux et identifiants.
- [Calendrier officiel](https://calendrier.api.gouv.fr/) et [jours fériés métropole 2026](https://calendrier.api.gouv.fr/jours-feries/metropole/2026.json) : accès JSON vérifié, 11 dates ; récupérer toutes les années du périmètre et conserver attribution et licence des données. Le [dépôt officiel](https://github.com/etalab/calendrier.api.gouv.fr#licences), consulté, distingue données sous Licence Ouverte et code sous MIT.
- [Météo-France - Données climatologiques de base horaires](https://www.data.gouv.fr/datasets/donnees-climatologiques-de-base-horaires) : source du sujet, à auditer si retenue ; observations futures réservées à l'analyse après coup.
- [Calendrier scolaire officiel](https://data.education.gouv.fr/explore/dataset/fr-en-calendrier-scolaire/information/) : piste du sujet si utile ; filtrer la zone et les dates, vérifier publication et jointure.

## 3. Fiche de lecture minimale à partager

Pour chaque méthode candidate : référence/version ; problème traité ; données et hypothèses ; disponibilité des entrées ; transfert possible ; adaptation proposée ; coûts et ressources ; code/poids/licence ; risques de contamination ; différence entre expérience publiée et nôtre ; comparaison réalisable en trois journées ; solution de remplacement.

E2 et E3 proposent les méthodes ; E4 vérifie que les expériences permettent les conclusions ; E5 confirme les conditions d'exécution. Les choix sont consignés avant l'examen du test final.
