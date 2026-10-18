# Ecolodge Sainte-Marie (Madagascar) — étude d'investissement + veille annonces

Business plan chiffré (rachat phasé d'un hôtel existant) + veille quotidienne des annonces de vente sur l'île.

## Contenu

| Dossier | Rôle |
|---|---|
| `model/` | Modèle Excel : Synthèse KPI, Scénario Rachat phasé (tranches, prêts dédiés, report déficitaire IS), scénario construction neuve (Hypothèses, CAPEX, Compte de résultat, Financement) |
| `config/sources.yaml` | Annonces surveillées (URL, ancre, prix de contrôle) |
| `src/scrape_listings.py` | Récupère les pages en direct, extrait prix + statut (actif / vendu / expiré) |
| `src/update_model.py` | Injecte le prix live de l'annonce principale dans `Scenario Rachat!C5` |
| `data/` | `listings.json` (état), `history.jsonl` (changements), `REPORT.md` (tableau lisible) |
| `.github/workflows/refresh.yml` | Exécution automatique chaque jour 06:00 UTC + commit des changements |

## Utilisation

```bash
pip install -r requirements.txt
python src/scrape_listings.py     # met à jour data/
python src/update_model.py        # met à jour le prix dans le modèle
```

Sur GitHub : onglet **Actions → refresh-listings → Run workflow** pour tester sans attendre le cron.
Excel recalcule les formules à l'ouverture du fichier (le script ne stocke pas les valeurs calculées).

## Limites à connaître

- **Scraping fragile** : si une agence change son site, le parseur peut rater un prix. La colonne *Contrôle* du rapport compare le prix trouvé au prix vérifié à la main (`expected_price`) : « à vérifier » = changement réel **ou** parsing cassé, à confirmer en ouvrant l'annonce.
- Un badge « VENDU » placé *avant* le titre d'un bien configuré en `price_side: after` n'est pas détecté.
- Certains sites bloquent les robots (ex. realigro) : ils sont exclus. Respecter les CGU des sites et garder une fréquence raisonnable (1x/jour).
- Le modèle repose sur des **hypothèses** (ADR, occupation, coûts), pas sur les comptes réels de l'hôtel. À remplacer dès réception des 3 derniers exercices.
- Ce dépôt n'est pas un conseil en investissement. Titre foncier à vérifier auprès des Domaines (Antananarivo) avant tout engagement.
