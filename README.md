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

Prérequis : Python 3.11+, Git.

```bash
# 1. Cloner le repo
git clone <repo-url> homelab && cd homelab

# 2. Créer un venv et installer les dépendances Python
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r ansible/requirements.txt

# 3. Installer les collections Ansible
cd ansible
ansible-galaxy collection install -r requirements.yml

# 4. Configurer le mot de passe vault
mkdir -p ~/.ansible
echo "<ton-vault-password>" > ~/.ansible/vault-pass-homelab.txt
chmod 0600 ~/.ansible/vault-pass-homelab.txt

# 5. Vérifier la chaîne
ansible-inventory --list
ansible-vault view inventory/group_vars/vps/vault.yml
ansible-lint
```

## Hooks pre-commit (recommandé)

```bash
pre-commit install
pre-commit run --all-files
```

## Conventions

Tout est codé dans `docs/adr/ADR-000-fondations-ansible.md`. Lis-le.

Commits : Conventional Commits, **aucun co-auteur IA**. Tous les commits au nom de `ldesfontaine`.

## État du projet

Voir la section « Roadmap » de [`docs/00-project-overview.md`](docs/00-project-overview.md#8-roadmap-haut-niveau-sans-dates) pour l'état d'avancement et la séquence des étapes restantes.

## Licence

MIT — voir `LICENSE`.
