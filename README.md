# homelab — `ldesfontaine.com`

Infrastructure as Code du homelab personnel `ldesfontaine.com`.

Toute la conception, les choix d'architecture et les contraintes sont dans le **cahier des charges** : [`docs/cahier-des-charges-homelab.md`](docs/cahier-des-charges-homelab.md).

## Documentation

- **Cahier des charges** : `docs/cahier-des-charges-homelab.md` — la vision et l'architecture cible
- **Décisions techniques (ADR)** : `docs/adr/` — l'ADR-000 est le document fondateur du repo Ansible, à lire avant toute contribution
- **Runbooks opérationnels** : `docs/runbooks/` — procédures de DR, mise à jour, rotation de secrets, etc.

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

- [x] Session 0 — bootstrap repo (structure, configs, vault)
- [ ] Session 1 — rôles `common` + `bootstrap` + détection SSH
- [ ] Session 2 — hardening + UFW + fail2ban
- [ ] Session 3 — docker + portfolio
- [ ] Session 4 — Pangolin
- [ ] Session 5 — CrowdSec
- [ ] Session 6 — WireGuard hub admin

## Licence

MIT — voir `LICENSE`.
