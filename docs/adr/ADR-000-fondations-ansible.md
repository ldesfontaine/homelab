# ADR-000 — Fondations du repo Ansible homelab

> **Document fondateur** — toute évolution du repo Ansible (rôles, playbooks, inventaire) DOIT respecter ces décisions. En cas de divergence : ce fichier fait foi. Toute exception est tracée dans un nouvel ADR.

> **Statut** : actif — `v1.2` — auteur `ldesfontaine`

---

## Périmètre

Ce repo va héberger **tout le code d'infrastructure** du homelab :

- VPS Hetzner (Pangolin, portfolio, CrowdSec, WG hub admin)
- Proxmox host (à venir)
- LXCs (Authentik, Vaultwarden, Filebrowser, Traefik interne, Newt, UniFi controller, etc.)
- OPNsense (via collection `ansibleguy.opnsense`)
- Proxmox Backup Server (Pi5)

Aujourd'hui on bootstrap juste le VPS, mais **chaque décision ci-dessous est prise pour que l'ajout des autres machines ne casse rien**.

---

## Décision 1 — Provisioning du VPS

**Décision** : provisioning **manuel** via la console Hetzner. Pas de Terraform pour l'instant.

**Justification** : Terraform ajoute une couche IaC qui n'a de sens qu'à partir de plusieurs VPS ou si on veut détruire/recréer fréquemment. Pour un VPS unique en production, c'est de la complexité prématurée. À reconsidérer si on a besoin d'un VPS cold-standby chez Scaleway/OVH (cf. cahier section 11 — mitigations SPOF).

**Conséquence** : Ansible se connecte à un VPS pré-existant. Le bootstrap initial est documenté dans `docs/runbooks/vps-bootstrap-manual.md`.

---

## Décision 2 — Approche Ansible : structure et conventions

**Décision** : **rôles autonomes, idempotents, sans dépendance croisée**. L'ordre d'exécution est piloté par les playbooks, **jamais** par les `meta/main.yml` des rôles.

**Règles non négociables** :

1. Chaque rôle est rejouable seul, avec des `defaults/main.yml` qui ont des valeurs sensibles par défaut.
2. **`--check` doit toujours retourner OK** sur un système en état stable. Un deuxième run = zéro change.
3. **Aucune `command:`/`shell:`** si un module existe. Quand c'est inévitable : `creates:`/`removes:` obligatoire.
4. **Pas de `meta: dependencies`**. Le `site.yml` orchestre l'ordre, c'est lisible et controllable.
5. **`become: false` par défaut** au niveau playbook ; `become: true` au niveau task seulement quand strictement nécessaire (principe de moindre privilège).
6. **`no_log: true`** sur toute task qui manipule un secret (vault, génération de clé, mot de passe).
7. **Tags partout** : tout rôle a au minimum un tag de son nom (`tags: [docker]`) pour `ansible-playbook site.yml --tags docker`.
8. **Handlers** pour les redémarrages de services — jamais de `notify` vers une tâche, toujours vers un handler nommé.
9. **`backup: yes`** sur tout module qui édite un fichier critique (template, lineinfile, copy).
10. **Validation avant reload** sur les services critiques : `validate: 'sshd -t -f %s'` pour sshd_config, `validate: 'nginx -t -c %s'` pour nginx, etc.
11. **Tous les modules de fichier (template/copy/file/lineinfile) ont `mode`, `owner`, `group` explicites**. Aucun fichier ne s'appuie sur le umask par défaut (cf. Décision 11).

**Conventions de nommage** :

| Élément | Convention | Exemple |
|---|---|---|
| Rôle maison | `<service>` ou `<service>-<role>` | `common`, `hardening`, `docker`, `pangolin`, `wg-admin-hub` |
| Tâche | Verbe à l'impératif, anglais | `Install Docker CE`, `Configure UFW default policy` |
| Handler | Verbe au gérondif | `restarting sshd`, `reloading ufw` |
| Variable | snake_case, préfixée par le nom du rôle (ou `homelab_` pour les globales) | `docker_compose_version`, `pangolin_admin_email`, `homelab_domain` |
| Fichier d'inventaire | snake_case | `hosts.yml`, `proxmox.yml` |
| Groupe Ansible | snake_case | `vps`, `lxc_services`, `role_docker` |

---

## Décision 3 — Inventaire : statique aujourd'hui, dynamic-ready demain

**Décision** : inventaire **multi-source** dès le départ. Aujourd'hui, un seul fichier statique. Demain, ajout transparent du dynamic inventory Proxmox.

**Structure** :

```
ansible/inventory/
├── 00-static.yml              # hosts statiques (VPS aujourd'hui, autres externes plus tard)
├── 01-proxmox.proxmox.yml     # AJOUTÉ EN PHASE PROXMOX (community.general.proxmox plugin)
└── group_vars/
    ├── all/
    │   ├── vars.yml           # variables communes à tous les hôtes (dont homelab_domain)
    │   └── vault.yml          # secrets communs chiffrés
    ├── vps/
    │   ├── vars.yml
    │   └── vault.yml
    └── lxc/                   # à venir
        └── vars.yml
```

**Pourquoi le préfixe numérique** : Ansible charge les fichiers d'inventaire dans l'ordre alphabétique. On veut que les statiques se chargent **avant** le dynamic, pour que les `group_vars` statiques puissent override les valeurs venant de Proxmox.

**Pourquoi le suffixe `.proxmox.yml`** : requis par le plugin `community.general.proxmox`.

**Phase Proxmox (futur)** : le plugin mappe les **tags Proxmox** vers des **groupes Ansible** préfixés `tag_<nom>`. Workflow : tu tagges une VM `docker` dans l'UI Proxmox → elle rejoint le groupe `tag_docker` → tu cibles ce groupe dans ton playbook. Aucun fichier d'inventaire à éditer à la main. Authentification via **API token Proxmox** chiffré dans vault.

---

## Décision 4 — Bootstrap SSH idempotent — clé uniquement + auto-détection du port

**Décision** : le bootstrap repose **uniquement sur la clé SSH** (jamais de password). Le port SSH est défini par variable, peut être différent par machine, et est **auto-détecté à chaque run** pour que n'importe quel playbook fonctionne quel que soit l'état de la machine.

### Pas de password — clé SSH only

- L'admin dépose sa clé SSH publique laptop dans `/root/.ssh/authorized_keys` du VPS via la console Hetzner (option à la création), AVANT de lancer Ansible.
- **Aucun password root, aucun password user n'est stocké dans le repo, ni en vault ni ailleurs.**
- Si la clé ne fonctionne pas, Ansible plante avec un message d'erreur explicite (cf. play `_detect-ssh.yml`).
- Conséquence : moins de surface d'attaque, moins de secrets à gérer, moins de fichiers à rotater.

### Ports SSH paramétrables par groupe ou machine

Variables canoniques dans `group_vars/all/vars.yml` :

```yaml
ssh_bootstrap_port: 22
ssh_bootstrap_user: root

ssh_target_user: ansible
# ssh_target_port n'a PAS de default global : chaque groupe ou hôte le définit
```

Override par groupe :

```yaml
# group_vars/vps/vars.yml
ssh_target_port: 2222

# group_vars/lxc/vars.yml (futur)
ssh_target_port: 22                # LXCs internes peuvent rester en 22 (réseau privé)
```

Inventaire :

```yaml
# inventory/00-static.yml
all:
  children:
    vps:
      hosts:
        vps-pangolin:
          ansible_host: <ip-publique>
          ansible_port: "{{ ssh_target_port }}"
          ansible_user: "{{ ssh_target_user }}"
```

### Auto-détection du port à chaque run

**Tout playbook** (site.yml, deploy-portfolio.yml, etc.) commence par inclure le play `_detect-ssh.yml` qui :

1. Probe le `ssh_target_port` avec `wait_for` depuis localhost
2. Si OK → continue avec les credentials cibles (normal, machine déjà bootstrapée)
3. Si KO → probe `ssh_bootstrap_port` :
   - Si OK → override `ansible_port`/`ansible_user` avec les credentials bootstrap (la machine n'a pas encore été bootstrapée OU on est en train de la rebootstraper)
   - Si KO → fail explicite avec message clair

Résultat : **on peut rejouer n'importe quel playbook à tout moment**, Ansible s'adapte tout seul.

### Le rôle `bootstrap` — séquence d'opérations critique

L'ordre est non négociable (un bug ici = perte de la machine) :

1. Probe avec `_detect-ssh` (le rôle reçoit `ansible_port`/`ansible_user` ajustés)
2. `apt update` (machine peut être fresh)
3. Création du user `{{ ssh_target_user }}` (clé SSH déployée, sudo NOPASSWD, mot de passe désactivé via `password: '!'`)
4. Installation et configuration UFW : deny incoming par défaut, **ouvre `ssh_target_port` ET `ssh_bootstrap_port` simultanément** pendant la transition
5. Configuration sshd : `Port {{ ssh_target_port }}`, `PermitRootLogin no`, `PasswordAuthentication no`, `PubkeyAuthentication yes`, `AllowUsers {{ ssh_target_user }}`
6. **`sshd -t`** validation — si KO, abort sans reload
7. Reload sshd
8. `meta: reset_connection`
9. Re-probe sur `ssh_target_port` avec credentials cibles
10. Si OK → ferme le `ssh_bootstrap_port` dans UFW
11. Si KO → fail (admin doit intervenir via console Hetzner)

**Conséquence importante** : la **clé publique SSH** de l'admin est dans `group_vars/all/vars.yml` (variable `admin_ssh_public_keys`, liste de clés). La **clé privée** n'est nulle part dans le repo.

### Limite acceptée — check mode partiel sur le bootstrap

Le rôle `bootstrap` n'est **pas entièrement dry-run-friendly** par construction. Chaque task agit sur un état créé par la précédente (user créé → `.ssh/` créé → `authorized_keys` créé → perms ajustées) ; en check mode, Ansible simule mais ne crée pas, donc les tasks suivantes échouent sur des modules qui exigent la présence réelle du fichier/user (ex : `ansible.builtin.file` avec `state: file`).

**Conséquence** : le dry-run `--check` du playbook `bootstrap.yml` plante typiquement au milieu du rôle `bootstrap`. **C'est attendu**, ce n'est pas un bug. La validation du rôle se fait via :
1. Run réel sur un VPS fresh
2. **2ème run** qui doit afficher `changed=0` (test d'idempotence — c'est le **vrai** test du bootstrap)

Cette limitation **ne s'applique qu'au rôle `bootstrap`**. Tous les rôles ultérieurs (common, docker, pangolin, etc.) doivent passer proprement en `--check --diff` sur un host déjà bootstrapé.

À reconsidérer plus tard : on pourrait ajouter `when: not ansible_check_mode` sur les tasks qui dépendent d'un état créé, mais le ROI est faible pour une opération unique par host.

---

## Décision 5 — Hardening : `devsec.hardening` + rôle custom

**Décision** : on **délègue le hardening lourd** (sshd ciphers/KEX/MACs, sysctl réseau, login.defs, etc.) à la collection officielle **`devsec.hardening`** (anciennement `dev-sec`), basée sur les benchmarks CIS et maintenue activement.

Notre rôle `hardening` maison fait **uniquement** ce qui n'est pas couvert par devsec ou ce qui est spécifique au cahier des charges :

- Configuration `unattended-upgrades` avec la politique stricte `Debian-Security` uniquement (cf. cahier 16.2)
- Banner de login custom
- Désactivation de services Debian inutiles (avahi, cups, etc.)
- Configuration `chrony` (concept critique 14.7 — sync horaire pour OIDC)

**Collections externes pinées dans `requirements.yml`** :

```yaml
collections:
  - name: devsec.hardening
    version: ">=10.0.0,<11.0.0"  # range mineur — sécurité upstream sans intervention
  - name: community.docker
    version: ">=3.10.0,<4.0.0"
  - name: community.general
    version: ">=10.0.0,<11.0.0"
  - name: ansible.posix
    version: ">=1.5.0,<2.0.0"
```

**Justification** : pas de réinvention de la roue, on bénéficie des audits CIS upstream, on remonte les updates upstream. Si devsec.hardening introduit un breaking change, le pin de version nous protège.

**Policy de pinning** : range mineur (`>=X.0.0,<X+1.0.0`) pour toutes les collections externes — permet les correctifs upstream (bugs, sécurité) sans intervention manuelle, tout en bloquant les bumps majeurs potentiellement breaking. Le `ansible/requirements.yml` est la source de vérité opérationnelle ; cette décision donne la policy.

---

## Décision 6 — Portfolio : image GHCR, pas de build sur le VPS

**Décision** : le rôle `portfolio` **pull** l'image `ghcr.io/ldesfontaine/portfolio:<tag>` depuis GHCR (image multi-stage déjà publiée par le CI GitHub Actions du repo portfolio, signée cosign). **Aucun build sur le VPS.**

**Justification** :

- Le build de l'image (Next.js + Payload + GoatCounter) prend ~4-5 min et nécessite Node 22 + libvips-dev. Aucune raison de polluer le VPS avec ça.
- Le CI portfolio gère déjà build + sign + push. C'est la source de vérité.
- Rollback trivial : on change `portfolio_image_tag` dans `group_vars/vps/vars.yml`, on rejoue le rôle.

**Variables clés du rôle** :

```yaml
portfolio_image: "ghcr.io/ldesfontaine/portfolio"
portfolio_image_tag: "0.1.0"                       # à incrémenter à chaque release
portfolio_data_volume: "portfolio-data"
portfolio_media_volume: "portfolio-media"
portfolio_payload_secret: "{{ vault_portfolio_payload_secret }}"
portfolio_site_url: "https://{{ homelab_fqdn_portfolio }}"
portfolio_goatcounter_vhost: "{{ homelab_fqdn_portfolio }}"
portfolio_container_port: 3000                      # interne au réseau Docker
```

**Réseau Docker** : le container portfolio est sur le **même réseau Docker que Pangolin**. Pas d'exposition de port sur l'host (`ports:` vide). Pangolin route directement via le DNS Docker interne.

**Sécurité container** : `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `tmpfs: [/tmp, /app/.next/cache]` — repris du compose de prod documenté dans le repo portfolio.

**Backup** : un cron sur l'hôte exécute `docker exec portfolio /app/scripts/backup.sh` chaque nuit (cf. README portfolio). Le rôle `portfolio` pose ce cron avec `mode: '0644'`, `owner: root`.

---

## Décision 7 — Reverse proxy public : Pangolin (Traefik embarqué)

**Décision** : sur le VPS, **Pangolin** est le seul reverse proxy public. Il embarque sa propre instance Traefik (cf. cahier section 5 — "Reverse proxy public : Traefik (embarqué dans Pangolin)").

**Conséquences** :

- **Aucun Traefik standalone** sur le VPS
- **Aucun label `traefik.*`** sur les containers applicatifs (portfolio, etc.) — c'est Pangolin qui déclare les ressources via son UI ou config file
- Les containers applicatifs exposent leur port **sur le réseau Docker interne uniquement** (pas de `ports:` mappés sur l'host)
- Pangolin gère **les certs Let's Encrypt** via DNS-01 Cloudflare (cf. cahier section 6 — un même cert wildcard public + interne)
- **Le bouncer CrowdSec** est un plugin Traefik intégré dans la stack Pangolin (cf. cahier phase 9 étape 5)

**Apex `{{ homelab_domain }}` → `{{ homelab_fqdn_portfolio }}`** : configuré dans Pangolin (deux hostnames sur la même ressource + middleware redirect), pas dans le compose portfolio. Les labels Traefik documentés dans le README portfolio sont à **ignorer** dans notre déploiement avec Pangolin.

---

## Décision 8 — Secrets : ansible-vault

**Décision** : **tous les secrets** sont chiffrés via `ansible-vault` dans des fichiers `vault.yml` dédiés. Jamais en clair dans Git.

**Convention** :

- Variables sensibles préfixées par `vault_` : `vault_portfolio_payload_secret`, `vault_cloudflare_api_token`, etc.
- Fichier `group_vars/<groupe>/vault.yml` chiffré
- Fichier `group_vars/<groupe>/vars.yml` en clair, qui **référence** les variables vault (`portfolio_payload_secret: "{{ vault_portfolio_payload_secret }}"`)

→ Le rôle ne voit jamais `vault_*` directement, il voit la variable applicative. Ça permet de scanner le code pour trouver les usages sans déchiffrer.

**Mot de passe vault** : stocké **hors du repo**, dans Bitwarden de transition (avant que Vaultwarden soit up — cf. cahier phase 0). Référence via `ansible.cfg` :

```ini
[defaults]
vault_password_file = ~/.ansible/vault-pass-homelab.txt
```

Ce fichier est dans le `.gitignore`. Procédure de récupération du mot de passe vault documentée dans `docs/runbooks/recover-vault-password.md`.

**Inventaire des secrets attendus** (à compléter au fur et à mesure) :

| Variable | Usage | Création |
|---|---|---|
| `vault_cloudflare_api_token` | DNS-01 pour Let's Encrypt (Pangolin + Traefik interne) | Manuel via dashboard Cloudflare, scope `Zone:DNS:Edit` |
| `vault_portfolio_payload_secret` | Signature sessions Payload CMS | `openssl rand -base64 48` |
| `vault_pangolin_admin_password` | Compte admin Pangolin initial | Généré aléatoirement à la création |
| `vault_proxmox_api_token` | Dynamic inventory Proxmox (futur) | Créé via UI Proxmox |

**Ne JAMAIS mettre en vault** :

- Passwords Linux (root, ansible, etc.) — la clé SSH suffit
- Clé privée WireGuard du VPS — elle reste sur le VPS, générée localement par `wg genkey` au bootstrap. Seule la clé **publique** est exportée vers le vault pour distribution aux peers.

**Rotation** : les tokens API (Cloudflare, GHCR, Pangolin admin) sont **rotated annuellement**. Procédure dans `docs/runbooks/rotate-secrets.md`.

---

## Décision 9 — Conventions de commit

**Décision** : commits **conventionnels** (Conventional Commits), signés, **sans co-auteur IA**.

**Format** :

```
<type>(<scope>): <description courte>

<corps optionnel>

<footer optionnel>
```

**Types autorisés** : `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `ci`

**Scopes typiques** : `vps`, `ansible`, `docker`, `hardening`, `pangolin`, `portfolio`, `crowdsec`, `wg`, `inventory`, `vault`

**Exemples** :

- `feat(hardening): add chrony role with timezone enforcement`
- `fix(pangolin): correct cloudflare DNS-01 resolver config`
- `docs(adr): clarify Décision 6 image pull strategy`

**Règles strictes** :

- **Aucun `Co-Authored-By` automatique** de la part d'agents IA (Claude Code, Copilot, Cursor, etc.). Tous les commits sont au nom de `ldesfontaine`. Si une partie du code a été générée par un agent IA, c'est tracé dans le **corps du commit** ("généré avec assistance Claude Code, relu et adapté"), pas dans un trailer `Co-Authored-By:`.
- **Pas de commit "WIP" sur `main`**. Les WIP vont sur des branches `feat/*`.
- **Pas de merge commit sur `main`** : rebase + fast-forward.
- **Tags `vX.Y.Z`** sur les états stables uniquement, après validation manuelle de la session.

**Configuration à passer dans chaque prompt à un agent IA** : on lui spécifie explicitement de ne pas ajouter de trailer `Co-Authored-By: Claude` ni de signer les commits en son nom.

---

## Décision 10 — Sécurité by design : check-list

À cocher avant tout merge sur `main` :

- [ ] `ansible-lint` passe (avec config dans `.ansible-lint`)
- [ ] `yamllint` passe (avec config dans `.yamllint`)
- [ ] `ansible-playbook --check --diff` passe sans modification sur un système en état stable (idempotence)
- [ ] Aucune `command:`/`shell:` sans `creates:`/`removes:`
- [ ] Aucun secret en clair (vérifié via `grep -r "password\|secret\|token" roles/ playbooks/`)
- [ ] `no_log: true` sur les tasks sensibles
- [ ] `validate:` sur les fichiers de conf critiques (sshd, nginx, ufw, etc.)
- [ ] `backup: yes` sur les édits de fichiers système critiques
- [ ] **`mode`/`owner`/`group` explicites sur tous les modules de fichier** (cf. Décision 11)
- [ ] Variables `vault_*` jamais référencées directement dans les rôles (toujours via une variable applicative dans `group_vars/`)
- [ ] Fichier `vault.yml` chiffré (`ansible-vault view` requiert le mot de passe)
- [ ] `.gitignore` couvre `*.retry`, `vault-pass*`, `.venv/`, `.cache/`, etc.
- [ ] Document de rollback documenté dans `docs/runbooks/` pour les changements impactant la prod
- [ ] **Aucune chaîne littérale `ldesfontaine.com` dans le code** — utilisation systématique de `homelab_domain`/`homelab_fqdn_*` (cf. Décision 12)

---

## Décision 11 — Permissions et propriété des fichiers — explicites toujours

**Décision** : tous les modules Ansible qui posent ou modifient un fichier (`template`, `copy`, `file`, `lineinfile`, `blockinfile`, `assemble`) DOIVENT spécifier `mode`, `owner`, `group` de manière **explicite**. Le umask par défaut n'est jamais une source acceptable.

**Conventions par type de fichier** :

| Type | mode | owner | group | Note |
|---|---|---|---|---|
| Conf système publique (sshd_config, ufw, sysctl.d) | `'0644'` | `root` | `root` | Lisible par tous |
| Conf système avec secret en clair | `'0600'` | `root` | `root` | unattended-upgrades patterns, etc. |
| Clé privée SSH | `'0600'` | propriétaire | propriétaire | Bloquant sinon ssh refuse |
| Clé publique SSH | `'0644'` | propriétaire | propriétaire | |
| Répertoire `.ssh/` | `'0700'` | propriétaire | propriétaire | |
| Fichier `authorized_keys` | `'0600'` | propriétaire | propriétaire | |
| Clé privée WireGuard (`/etc/wireguard/*.conf`) | `'0600'` | `root` | `root` | Contient PrivateKey |
| docker-compose.yml | `'0644'` | `root` | `root` | |
| Fichier `.env` Docker (secrets de runtime) | `'0600'` | `root` | `root` | |
| Répertoire de volume Docker (bind-mount) | `'0700'` ou ad-hoc | uid du container | gid du container | Selon le service |
| Script shell exécutable | `'0755'` | `root` | `root` | |
| Fichier de log (touché par Ansible) | `'0640'` | service | adm | |
| Crontab `/etc/cron.d/*` | `'0644'` | `root` | `root` | |
| Banner de login (`/etc/issue.net`) | `'0644'` | `root` | `root` | |
| Fichier `.profile`/`.bashrc` user | `'0644'` | user | user | |

**Mode en notation octale** : toujours **chaîne entre guillemets** (`'0644'`), jamais en entier (`0644`) pour éviter les pièges de l'octal implicite YAML.

**Exemple correct** :

```yaml
- name: Deploy sshd_config
  ansible.builtin.template:
    src: sshd_config.j2
    dest: /etc/ssh/sshd_config
    owner: root
    group: root
    mode: '0644'
    backup: yes
    validate: '/usr/sbin/sshd -t -f %s'
  notify: restarting sshd
```

**Exemple incorrect** (refusé en lint) :

```yaml
- name: Deploy sshd_config
  ansible.builtin.template:
    src: sshd_config.j2
    dest: /etc/ssh/sshd_config
    # pas de mode/owner/group → umask par défaut, comportement imprévisible
```

---

## Décision 12 — Domaine en variable — jamais hardcodé

**Décision** : aucune chaîne littérale `ldesfontaine.com` ou subdomain littéral dans le code. Tout passe par des variables centralisées dans `group_vars/all/vars.yml`.

**Variables canoniques** :

```yaml
# group_vars/all/vars.yml

# Domaine racine — modifier ici si on change de domaine un jour
homelab_domain: "ldesfontaine.com"

# Sous-domaines (centralisés pour faciliter renommage)
homelab_subdomain_portfolio: "portfolio"
homelab_subdomain_vault: "vault"
homelab_subdomain_files: "files"
homelab_subdomain_auth: "auth"

# FQDN construits — utiliser ces variables partout
homelab_fqdn_portfolio: "{{ homelab_subdomain_portfolio }}.{{ homelab_domain }}"
homelab_fqdn_vault: "{{ homelab_subdomain_vault }}.{{ homelab_domain }}"
homelab_fqdn_files: "{{ homelab_subdomain_files }}.{{ homelab_domain }}"
homelab_fqdn_auth: "{{ homelab_subdomain_auth }}.{{ homelab_domain }}"
```

**Règles** :

- Tous les rôles utilisent `{{ homelab_fqdn_* }}` ou `{{ homelab_domain }}`. **Jamais** de littéral `ldesfontaine.com` ailleurs.
- Le check-list Décision 10 contient une étape de vérification : `grep -rE "ldesfontaine\.(com|fr|dev)" roles/ playbooks/ templates/` doit retourner zéro résultat (sauf dans `group_vars/all/vars.yml` qui est la source de vérité).
- Le **token API Cloudflare** est lié à la zone DNS. Si le domaine change, il faut le rotater. Procédure dans `docs/runbooks/change-domain.md` (à créer quand applicable).

**Test** : pour valider le respect de cette règle, un hook pre-commit (à ajouter) peut faire le grep et refuser le commit s'il trouve une occurrence interdite.

---

## Outils du repo

- `ansible-core` ≥ 2.17 (Python 3.11+ requis pour la dernière)
- `ansible-lint` ≥ 24.x
- `yamllint` ≥ 1.35
- `pre-commit` (hooks : ansible-lint, yamllint, no-secrets, detect-private-key, check-no-literal-domain)
- `ansible-vault` (bundled avec ansible-core)
- `python3 -m venv .venv` à la racine du repo, `.venv/` dans `.gitignore`

Versions exactes pinées dans `requirements.txt` et `requirements.yml`.

---

## Évolutions futures (anti-patterns à éviter)

- ❌ Ajouter Watchtower ou auto-pull Docker : **interdit par le cahier** (16.2). Updates Docker manuels.
- ❌ Mettre des secrets en `extra-vars` sur la CLI : laisse des traces dans l'historique shell. Toujours via vault.
- ❌ Utiliser `community.crypto.openssh_keypair` pour générer la clé WG du VPS et la stocker en clair : la clé privée WG **reste sur le VPS**. Seule la clé publique est exportée vers le vault pour distribution aux peers.
- ❌ Faire dépendre un rôle d'un autre via `meta/main.yml`. Si tu te retrouves à vouloir ça, c'est qu'il faut refactorer en deux playbooks.
- ❌ Modifier l'inventaire à la main quand Proxmox sera up : tags Proxmox = source de vérité.
- ❌ Stocker un password root, sudo password, ou autre mot de passe Linux dans le vault : on n'en a pas besoin, clé SSH suffit. Le seul cas où un password peut transiter par le vault, c'est un secret applicatif (Payload secret, Pangolin admin, etc.).
- ❌ Hardcoder `ldesfontaine.com` (ou sous-domaine littéral) dans un rôle, template ou playbook. Variables `homelab_*` uniquement.

---

## Changelog

| Date | Version | Changement |
|---|---|---|
| (2026-05-15) | 1.0 | Création initiale — fondations Ansible homelab |
| (2026-05-15) | 1.1 | Décision 4 : suppression du password root du vault, clé SSH uniquement, auto-détection du port via `_detect-ssh.yml`. Ajout Décision 11 (permissions/propriété fichiers explicites). Ajout Décision 12 (domaine en variable). Mise à jour Décision 8 inventaire des secrets attendus (sans password Linux). Anti-patterns enrichis. (Note v1.2 : ces sections s'appelaient encore "ADR-XXX" lors de la rédaction de v1.1.) |
| 2026-05-16 | 1.2 | Renommage des sections internes "ADR-XXX" → "Décision X" pour éviter la confusion avec les fichiers ADR du dossier `docs/adr/`. Alignement du pin `devsec.hardening` avec `ansible/requirements.yml` (range mineur). Ajout policy de pinning. |