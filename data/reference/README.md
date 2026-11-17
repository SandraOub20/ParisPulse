# Référentiels - équipe 1

Données de contexte fournies telles quelles. **Chaque équipe fait sa propre jointure** avec les comptages.

## `greves_transport_idf.csv` - y a-t-il grève ce jour-là ?

Une ligne par jour, du 01/01/2023 au 17/11/2026 (1 417 jours, dont 73 de grève).

| Colonne | Contenu |
| --- | --- |
| `date` | jour, heure de Paris (AAAA-MM-JJ) |
| `greve` | `true` si les transports en commun d'Île-de-France (RATP, RER, Transilien) ont été perturbés par une grève ce jour-là, sinon `false` |

**Jointure :** date locale (Europe/Paris) de l'heure de comptage = `date`. En dehors de la période, la valeur est inconnue.

**Pour une prévision :** une grève est annoncée au moins 24 h avant (Code des transports, art. L1222-8). On peut donc l'utiliser pour prévoir le jour même.

## `greves_transport_idf_sources.csv` - justification des jours de grève

Une ligne par jour de grève, avec la page source datée (`source_url`) et le détail : portée, réseaux, intensité, description, date du préavis et confiance.

Il n'existe pas d'API d'historique des grèves : la liste a été constituée à la main, à partir des pages RATP, Transilien, Citymapper et de la presse.

**Limites :**
- le recensement peut être incomplet : grèves de bus 2023-2025, janvier-avril 2025 et février-mai 2026 sont mal couverts ;
- l'effet sur le vélo n'a pas été mesuré.
