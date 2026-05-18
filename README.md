# homelab — `ldesfontaine.com`

Infrastructure as Code du homelab personnel `ldesfontaine.com`.

Conception, architecture, doctrines, roadmap et inventaire des
secrets : [`docs/00-project-overview.md`](docs/00-project-overview.md).

## Documentation

- **Source de vérité opérationnelle** : [`docs/00-project-overview.md`](docs/00-project-overview.md) — mission, architecture, doctrines, roadmap, inventaire des secrets.
- **Décisions techniques (ADR)** : [`docs/adr/`](docs/adr/) — ADR-000 est le document fondateur du repo Ansible, à lire avant toute contribution.
- **Runbooks opérationnels** : [`docs/runbooks/`](docs/runbooks/) — procédures de DR, mise à jour, rotation de secrets, etc.
- **Inventaire des secrets** : [`docs/secrets-inventory.md`](docs/secrets-inventory.md) — doctrine, emplacements, procédure de récupération sur nouvelle machine.
- **Référence historique** : [`docs/cahier-des-charges-homelab.md`](docs/cahier-des-charges-homelab.md) — cahier des charges initial (conception), conservé pour traçabilité.

## Stack

- Ansible (rôles autonomes, idempotents, sans dépendance croisée)
- Proxmox VE (à venir)
- OPNsense (à venir)
- Pangolin (frontal public, Traefik embarqué)
- CrowdSec, Authentik, Vaultwarden, Filebrowser, Newt

## Setup local

Prérequis : Python 3.11+, Git, accès au gestionnaire de mots de
passe (cf. [`docs/secrets-inventory.md`](docs/secrets-inventory.md)).

```bash
git clone git@github.com:ldesfontaine/homelab.git
cd homelab
./scripts/setup.sh
```

Le script crée le venv Python, installe les dépendances et les
collections Ansible, installe les hooks pre-commit, et lance une
vérification de la chaîne complète. Il est idempotent — relançable
sans risque.

Pour configurer les secrets (vault password Ansible, clé age maître,
clés SSH/WG), suivre la procédure « Récupération sur nouvelle machine »
dans [`docs/secrets-inventory.md`](docs/secrets-inventory.md).

## Conventions

Tout est codé dans `docs/adr/ADR-000-fondations-ansible.md`. Lis-le.

Commits : Conventional Commits, **aucun co-auteur IA**. Tous les commits au nom de `ldesfontaine`.

## État du projet

Voir la section « Roadmap » de [`docs/00-project-overview.md`](docs/00-project-overview.md#8-roadmap-haut-niveau-sans-dates) pour l'état d'avancement et la séquence des étapes restantes.

## Licence

MIT — voir `LICENSE`.
