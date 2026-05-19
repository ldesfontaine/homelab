# Documentation du homelab

Index des documents du repo `ldesfontaine/homelab`.

## Point d'entrée

[`00-project-overview.md`](00-project-overview.md) — source de vérité
opérationnelle : mission, architecture, doctrines, roadmap, inventaire
des secrets. À lire en premier.

## Décisions techniques (ADRs)

[`adr/`](adr/) — décisions structurantes du projet, format ADR. ADR-000
est le document fondateur du repo Ansible. Lecture obligatoire avant
toute contribution.

## Runbooks de déploiement

[`runbooks/`](runbooks/) — procédures pas-à-pas pour déployer le VPS
et ses services. Sessions 1-6 couvrent le VPS complet (bootstrap,
hardening, Docker + portfolio, Pangolin + DNS, CrowdSec, WG admin hub).
Sessions à venir documenteront OPNsense, Proxmox, etc. au fur et à
mesure de leur déploiement.

**Convention** : un runbook par session de déploiement, dans l'ordre
chronologique. Chaque runbook contient prérequis, validation pré-vol,
procédure d'exécution, post-run validation, rollback, limites connues.

## Procédures opérationnelles

[`operations/`](operations/) — procédures récurrentes indépendantes
des sessions de déploiement :

- [`key-rotation.md`](operations/key-rotation.md) — rotation des
  secrets par type.
- [`backup-restore.md`](operations/backup-restore.md) — backup et
  restauration par composant.
- [`disaster-recovery.md`](operations/disaster-recovery.md) — DR
  scénarios.

**Différence avec runbooks/** : un runbook se joue une fois pour
mettre en place un composant. Une procédure operations se joue
périodiquement (rotation annuelle) ou ponctuellement (incident DR).

## Inventaires et schémas

- [`secrets-inventory.md`](secrets-inventory.md) — inventaire complet
  des secrets : doctrine, emplacements, procédure de récupération sur
  nouvelle machine.
- [`wg-admin-profiles.md`](wg-admin-profiles.md) — doctrine des
  profils peers du tunnel WG admin.
- [`schema-logique.svg`](schema-logique.svg) — schéma logique de
  l'architecture.
- [`schema-physique.svg`](schema-physique.svg) — schéma physique.
- [`configs/inventaire-physique.md`](configs/inventaire-physique.md) —
  inventaire du matériel (WIP).

## Référence historique

[`cahier-des-charges-homelab.md`](cahier-des-charges-homelab.md) —
cahier des charges initial (conception). Conservé pour traçabilité
de l'intention initiale ; le project-overview est la SoT actuelle.
