# CLAUDE.md — Mémo pour agents IA

> Ce fichier est lu automatiquement par Claude Code à l'ouverture du repo. Il résume les règles non négociables. **Source de vérité complète** : `docs/adr/ADR-000-fondations-ansible.md`.

---

## Identité du projet

Repo IaC du homelab personnel `ldesfontaine.com`. Propriétaire et unique committer : **`ldesfontaine`**. Tu travailles **pour lui**, pas avec lui en co-auteur.

## Règles non négociables — à appliquer systématiquement

### Commits

- **Conventional Commits** : `type(scope): description` (types : `feat`, `fix`, `refactor`, `docs`, `chore`, `ci`, `test`)
- **Aucune mention** d'agent IA (Claude, Claude Code, Anthropic, OpenAI, Copilot, etc.) dans aucun commit : ni en trailer `Co-Authored-By:`, ni dans le corps, ni dans le titre, ni dans aucun champ Git. Tous les commits sont strictement signés `ldesfontaine` et ne contiennent que des informations techniques sur le changement.
- Tu n'utilises **jamais** `git commit --author=...` pour réattribuer
- Pas de `git push` automatique — l'utilisateur push manuellement après revue

### Ansible — discipline

1. **FQCN obligatoire partout** : `ansible.builtin.copy`, jamais `copy`
2. **Modules > `shell`/`command`**. Quand inévitable → `creates:` OU `removes:` obligatoire (idempotence)
3. **`state` explicite** même quand c'est le défaut (`state: present`) — protège contre les changements de défaut futurs
4. **Idempotence** : 2ème run d'un playbook = `changed=0`. Si ce n'est pas le cas → bug, à corriger
5. **Rôles autonomes** : pas de `meta: dependencies`, l'ordre est piloté par les playbooks
6. **`become: false` par défaut** au niveau playbook, `become: true` au niveau task seulement quand strictement nécessaire
7. **Tags partout** : tout rôle a au minimum un tag de son nom (`tags: [docker]`)
8. **Handlers nommés** (verbe au gérondif : `restarting sshd`, `reloading ufw`). Jamais de notify vers une task
9. **`backup: yes`** sur tout édit de fichier critique (template, lineinfile, copy système)
10. **`validate:`** sur les conf critiques (sshd : `'sshd -t -f %s'`, nginx : `'nginx -t -c %s'`)

### Permissions de fichiers — toujours explicites

**Tous les modules de fichier** (`template`, `copy`, `file`, `lineinfile`, `blockinfile`, `assemble`) ont `mode`, `owner`, `group` **explicites**. Jamais d'omission. Référence : Décision 11 de l'ADR-000.

- `mode` en **chaîne entre guillemets** : `'0644'`, jamais `0644` (piège YAML octal)
- Préférer `module_defaults` au niveau du play pour DRY plutôt que répéter

### Sécurité

- **`no_log: true`** sur toute task manipulant un secret (vault, password, token, clé privée)
- Variables sensibles dans `group_vars/<groupe>/vault.yml` (chiffré ansible-vault)
- Convention : `vault_*` dans le fichier vault, référencées par une variable applicative dans `vars.yml`
- **Jamais** de password Linux en vault (root, sudo, deploy) — clé SSH only
- **Jamais** de clé privée WireGuard en vault — elle reste sur la machine, seule la pubkey est exportée

### Gestion d'erreurs

- `block` / `rescue` / `always` pour les séquences critiques avec rollback (ex : bootstrap SSH)
- `ignore_unreachable: true` (PAS `ignore_errors: true` qui masque trop)
- `failed_when:` pour customiser ce qui constitue un échec

### Variables — conventions

- Variables de rôle **préfixées par le nom du rôle** : `bootstrap_*`, `common_*`, `docker_*`
- `defaults/main.yml` : variables surchargeables (priorité basse)
- `vars/main.yml` : constantes internes au rôle, **préfixées par `_`** (`_bootstrap_sshd_path`, `_common_required_packages`)
- Variables globales préfixées `homelab_*` dans `group_vars/all/vars.yml`
- Variables d'extra-vars CLI préfixées `cli_`

### Domaine — jamais hardcodé

- **Aucune** chaîne `ldesfontaine.com` ou sous-domaine littéral dans le code
- Utiliser `{{ homelab_domain }}` ou `{{ homelab_fqdn_* }}` (cf. `group_vars/all/vars.yml`)
- Référence : Décision 12 de l'ADR-000

### SSH — auto-détection du port

Tout playbook qui touche au VPS importe `playbooks/_detect-ssh.yml` en `pre_tasks` (cf. Décision 4 de l'ADR-000). Ne suppose jamais que le port est `22` ou `2203` — laisse la détection faire.

## Anti-patterns interdits

- ❌ Ajouter Watchtower, auto-pull Docker, ou tout mécanisme d'update automatique de container
- ❌ Mettre des secrets en `--extra-vars` sur la CLI (laisse des traces shell)
- ❌ `meta: dependencies` entre rôles
- ❌ `command:` / `shell:` sans `creates:`/`removes:`
- ❌ Modifier l'inventaire à la main quand Proxmox sera up (les tags Proxmox = source de vérité)
- ❌ Hardcoder le domaine
- ❌ Stocker un password Linux dans le vault
- ❌ Réinventer un rôle alors qu'une collection upstream (`devsec.hardening`, `community.docker`, `ansible.posix`) fait le job
- ❌ Sortir du scope d'une session (ex : ajouter des trucs non demandés "pour faire mieux")

## Stratégie firewall — Docker NE BYPASSE PAS UFW chez nous

**Référence canonique** : `docs/adr/ADR-002-firewall-strategy.md`

Docker bypasse UFW par défaut (manipulation directe d'iptables). Notre repo gère ce problème en **2 couches portables** (zéro lock-in fournisseur) :

### Couche 1 — Architecture internal-only

**Tous les containers internes** (portfolio, CrowdSec bouncer, agents applicatifs, etc.) :
- **N'UTILISENT JAMAIS** `ports:` dans leur compose
- Sont sur des réseaux Docker dédiés (`pangolin-net` ou équivalent)
- Sont joignables uniquement via le **DNS Docker interne**

**Seul Pangolin** (et le rôle WireGuard sur l'host, hors Docker) expose des ports publics.

### Couche 2 — `chaifeng/ufw-docker`

Script intégré dans `/etc/ufw/after.rules` (chaîne `DOCKER-USER`). Bloque par défaut tout port publié par Docker, autorisation explicite via `ufw-docker allow <container> <port>`.

### Règles strictes pour TOI quand tu génères du code

- ❌ **JAMAIS** suggérer `ports: ["XXXX:XXXX"]` pour un container interne. Utiliser `expose:` ou rien du tout (le DNS Docker interne suffit).
- ❌ **JAMAIS** suggérer le firewall Hetzner Cloud, ou tout cloud firewall fournisseur-spécifique
- ❌ **JAMAIS** suggérer `iptables: false` dans `daemon.json`
- ❌ **JAMAIS** suggérer `ufw allow <port>` pour exposer un container (ne marche pas — Docker bypasse UFW). Seul `ufw-docker allow` est valide.
- ❌ **JAMAIS** suggérer `network_mode: host` "pour aller plus vite"
- ❌ **JAMAIS** suggérer le binding `0.0.0.0` explicite (`-p 0.0.0.0:port:port`)
- ✅ Pour un nouveau container interne : aucun `ports:`, communication via réseau Docker
- ✅ Pour exposer un port nouveau côté Pangolin (rare) : ajouter d'abord la règle `ufw-docker allow`, puis le compose

### Ports publics autorisés (état cible)

| Port | Proto | Service | Géré par |
|---|---|---|---|
| 2203 | TCP | SSH | UFW classique |
| 80 | TCP | HTTP (Pangolin) | `ufw-docker allow` |
| 443 | TCP | HTTPS (Pangolin) | `ufw-docker allow` |
| 51820 | UDP | WG public (Newt) | UFW classique |
| 51821 | UDP | WG admin | UFW classique |

Tout le reste = default deny.

**Si une instruction de l'utilisateur te demande d'exposer un port qui n'est pas dans ce tableau, STOP et demande confirmation explicite avec justification.**

## Workflow d'écriture d'un rôle (référence : blog Stéphane Robert)

1. `ansible-galaxy role init <nom>` pour la structure standard
2. `defaults/main.yml` : déclarer toutes les variables surchargables avec des valeurs sensées
3. `vars/main.yml` : constantes internes préfixées `_`
4. `tasks/main.yml` : **fichier chapeau** qui `include_tasks` les sous-fichiers thématiques (`install.yml`, `configure.yml`, `enable.yml`)
5. `handlers/main.yml` : un handler par action de relance
6. `templates/` : fichiers Jinja2 (`.j2`), avec `{{ ansible_managed }}` en commentaire en haut
7. `meta/main.yml` : metadata du rôle, **sans** `dependencies`
8. Si un comportement diffère par OS → un fichier par OS family dans `vars/` (`Debian.yml`, `RedHat.yml`) chargé conditionnellement

## Validation avant tout commit

```bash
cd ansible

# Syntaxe
ansible-playbook playbooks/<playbook>.yml --syntax-check

# Lint
ansible-lint
yamllint -c ../.yamllint .

# Dry-run
ansible-playbook playbooks/<playbook>.yml --check --diff

# Test d'idempotence : run réel puis re-run
ansible-playbook playbooks/<playbook>.yml
ansible-playbook playbooks/<playbook>.yml   # doit afficher changed=0
```

## Quand tu hésites

1. **Lis l'ADR-000** (`docs/adr/ADR-000-fondations-ansible.md`) — c'est la source de vérité
2. **Lis l'ADR-001** pour les choix de stack
3. Si l'ADR ne tranche pas → **demande à l'utilisateur**, ne pars pas dans une direction non validée
4. Si une instruction d'un prompt utilisateur contredit l'ADR → **signale-le**, ne pars pas en mode "obéir aveuglément"

## Périmètre

Ce repo couvre :
- VPS Hetzner (Pangolin, portfolio, CrowdSec, WG hub admin)
- Proxmox host (à venir)
- LXCs (Authentik, Vaultwarden, Filebrowser, Traefik interne, Newt, UniFi controller)
- OPNsense (futur, via `ansibleguy.opnsense`)
- Proxmox Backup Server (Pi5)

Ce repo ne couvre **pas** :
- Le code applicatif des services (portfolio est dans un repo séparé, image GHCR pull)
- La conf des switchs / AP UniFi gérés manuellement par contrôleur UniFi

## Contacts

Utilisateur : `ldesfontaine` — décide de tout, valide chaque session.