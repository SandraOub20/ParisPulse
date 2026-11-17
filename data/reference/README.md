# Référentiels - équipe 1

Données de contexte fournies telles quelles. **Chaque équipe fait sa propre jointure** avec les comptages.

## `greves_transport_idf.csv` - y a-t-il grève ce jour-là ?

Une ligne par jour, du 01/01/2023 au 17/11/2026 (1 417 jours, dont 73 de grève).

| Colonne | Contenu |
| --- | --- |
| `date` | jour, heure de Paris (AAAA-MM-JJ) |
| `greve` | `true` si les transports en commun d'Île-de-France (RATP, RER, Transilien) ont été perturbés par une grève ce jour-là, sinon `false` |

```
date,greve
2026-11-04,false
2026-11-05,true
2026-11-06,false
```

**Jointure.** On convertit l'heure de comptage en heure de Paris, puis on joint sa date sur `date`. Attention au décalage :

| `timestamp` de counts.csv (UTC) | heure de Paris | `greve` |
| --- | --- | --- |
| 2026-11-04T22:00:00+00:00 | 04/11 23 h | false |
| 2026-11-04T23:00:00+00:00 | **05/11** 00 h | **true** |

En dehors de la période recensée, la valeur est inconnue.

**Peut-on l'utiliser pour prévoir ?** Oui : on n'a pas à prédire une grève, elle est connue à l'avance. Il faut cependant distinguer trois moments :

| Moment | Quand | Ce qu'on sait |
| --- | --- | --- |
| Annonce syndicale (grandes journées) | souvent 2 à 4 semaines avant | qu'une grève aura lieu, pas son ampleur |
| Préavis légal (services publics) | au moins 5 jours avant | qu'une grève est possible ; un préavis n'entraîne pas toujours de perturbation |
| Prévision de trafic RATP/SNCF | au plus tard 24 h avant (Code des transports, art. L1222-8) | lignes et niveau de perturbation |

Ici, `greve = true` veut dire « trafic annoncé comme perturbé ». On considère donc l'information connue **24 h avant** : pour une prévision faite à minuit le jour J, la valeur de J et celle de J+1 sont utilisables.

## `greves_transport_idf_sources.csv` - justification des jours de grève

Une ligne par jour de grève, avec la page source datée (`source_url`) et le détail : portée, réseaux, intensité, description, date du préavis et confiance.

Il n'existe pas d'API d'historique des grèves : la liste a été constituée à la main, à partir des pages RATP, Transilien, Citymapper et de la presse.

**Limites :**
- le recensement peut être incomplet : grèves de bus 2023-2025, janvier-avril 2025 et février-mai 2026 sont mal couverts ;
- l'effet sur le vélo n'a pas été mesuré.
