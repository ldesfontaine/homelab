# Homelab `ldesfontaine` — Vue d'ensemble du projet

Document de référence du projet. Ce fichier remplace l'ancien cahier des
charges comme source de vérité opérationnelle. Le cahier des charges
historique reste consultable pour les choix de conception passés.

---

## 1. Mission

Construire et opérer une infrastructure personnelle auto-hébergée combinant :

- **Une présence publique sobre** (portfolio statique sur `ldesfontaine.com`,
  derrière un reverse proxy durci),
- **Des services privés pour la famille** (gestion de mots de passe, fichiers,
  identité unifiée),
- **Une plateforme d'expérimentation maîtrisée** pour pratiquer le DevSecOps
  sur du matériel réel.

Le projet est piloté en *Infrastructure as Code* (Ansible) avec une doctrine
de reproductibilité totale : tout doit pouvoir être redéployé depuis le repo
Git plus la doc.

---

## 2. Architecture — trois couches indépendantes

```
┌────────────────────────────────────────────────────────────────┐
│  COUCHE 1 — VPS Hetzner (face Internet)                        │
│                                                                │
│  • Pangolin (reverse-proxy SaaS) + Gerbil (tunnel)             │
│  • Traefik v3 + plugin CrowdSec bouncer                        │
│  • Portfolio Next.js + Payload CMS                             │
│  • CrowdSec (community blocklists + bouncer Traefik)           │
│  • WireGuard hub admin (peers laptop, phone, OPNsense)         │
│                                                                │
│  Indépendance : se déploie en isolation totale. Les tunnels    │
│  attendent les peers, le portfolio est servi sans dépendance   │
│  vivante au homelab maison.                                    │
└────────────────────────────────────────────────────────────────┘
                            ▲
                            │ tunnels WireGuard sortants
                            │ (depuis la maison vers le VPS)
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  COUCHE 2 — Firewall OPNsense (frontière maison)               │
│                                                                │
│  • Bare-metal CWWK N150 fanless, 6 ports igc                   │
│  • Segmentation VLAN stricte (MGMT, LAN, IOT, EXPOSED,         │
│    SVC_PRIV, LAB, BACKUP)                                      │
│  • Unbound récursif + blocklists (StevenBlack, OISD, ThreatFox)│
│  • WG-ADMIN-CLIENT (sortant vers VPS hub)                      │
│  • LiveBox fermée à 100 % (zéro port forward, zéro DMZ)        │
│                                                                │
│  Indépendance : si le VPS est HS, OPNsense continue à router   │
│  et filtrer le trafic LAN. Seul l'accès admin externe est      │
│  perdu temporairement.                                         │
└────────────────────────────────────────────────────────────────┘
                            ▲
                            │ trunk VLAN (igc3) via switch L2
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  COUCHE 3 — Hyperviseur Proxmox (services internes)            │
│                                                                │
│  • Bare-metal HP Mini PC                                       │
│  • Bridge Linux VLAN-aware                                     │
│  • LXC services privés (Authentik, Vaultwarden, Filebrowser,   │
│    Traefik interne) sur VLAN SVC_PRIV                          │
│  • LXC Newt (tunnel WG-PUB vers Gerbil) sur VLAN EXPOSED       │
│                                                                │
│  Indépendance : si OPNsense ou VPS sont HS, les LXCs           │
│  continuent à tourner. La connectivité externe est dégradée    │
│  mais l'état interne est préservé.                             │
└────────────────────────────────────────────────────────────────┘
```

**Règle d'or** : chaque couche se déploie *sans dépendance vivante* sur les
autres. Les tunnels WireGuard peuvent rester en attente sans empêcher le
déploiement de leur extrémité. Idempotence et tolérance à l'attente sont
des contraintes de conception.

---

## 3. Doctrines structurantes

### 3.1 Fresh-install ready

Toute la stack doit être redéployable depuis zéro à partir de :

- Le repo Git (`github.com/ldesfontaine/homelab`)
- Les secrets backupés hors repo (vault password, clé age maître)
- Les backups de configuration OPNsense (`backups/opnsense/*.xml.age`)
- Le matériel physique vierge ou un VPS neuf

Aucune connaissance tribale, aucune étape "ah oui j'avais cliqué là il y a
trois mois". Si une procédure n'est pas dans le repo, elle n'existe pas.

### 3.2 Indépendance des couches

Voir l'architecture ci-dessus. Chaque couche se déploie dans n'importe
quel ordre, et tolère que les autres soient absentes au moment du
déploiement.

### 3.3 Secrets management

Deux mécanismes distincts, complémentaires :

| Mécanisme | Usage | Stockage |
|---|---|---|
| **ansible-vault** | Variables Ansible (mots de passe, tokens, pubkeys peers) | Dans le repo, sous `inventory/group_vars/<group>/vault.yml` |
| **age** | Fichiers larges ou binaires (backups XML OPNsense, archives clés) | Dans le repo (`.age`) ou hors repo selon le cas |

Pré-requis pour rendre cela sûr sur un repo **public** :

- Hook `pre-commit` avec `gitleaks` qui bloque tout commit contenant un
  secret en clair.
- Hook `detect-private-key` qui matche `-----BEGIN.*PRIVATE KEY-----`.
- `.gitignore` strict sur les `.xml`, `.key`, `.pem` non chiffrés.
- Vault password Ansible et clé age maître stockées dans un gestionnaire
  de mots de passe externe (Dashlane).

### 3.4 Documentation comme code

La documentation est versionnée dans le repo, à côté du code. Toute
modification structurelle s'accompagne d'une mise à jour de la doc dans
le même commit. Les procédures opérationnelles sont des fichiers
markdown actionnables, pas des descriptions narratives.

Trois niveaux de documentation cohabitent :

- **Architecture** (`docs/00-project-overview.md` — ce fichier) : la
  vision haute et les doctrines.
- **Déploiement** (`docs/deployment/*.md`) : procédures pas-à-pas pour
  installer une couche from scratch.
- **Opérations** (`docs/operations/*.md`) : rotations, backups, DR,
  diagnostics.
- **ADR** (`docs/adr/ADR-*.md`) : décisions structurantes avec leur
  justification.
- **Runbooks** (`docs/runbooks/session-*.md`) : journaux d'exécution des
  sessions, pour la traçabilité historique.

---

## 4. Stack technique

| Couche | Composants |
|---|---|
| **Virtualisation** | Proxmox VE (LXC + KVM) |
| **Conteneurs** | Docker Engine sur le VPS uniquement |
| **Réseau / Sécurité** | OPNsense (firewall, VLAN, Unbound, WireGuard client), CrowdSec (VPS) |
| **Reverse proxy** | Pangolin + Traefik (VPS, public), Traefik (LXC interne, privé) |
| **Tunnels** | WireGuard (3 instances : WG-PUB Newt, WG-ADMIN-RELAY admin, WG-MON futur) |
| **Identité** | Authentik (SSO OIDC, MFA) |
| **Mots de passe** | Vaultwarden |
| **Fichiers** | Filebrowser Quantum |
| **Automation** | Ansible (Galaxy collections, Jinja2 templates) |
| **Secrets** | ansible-vault, age, pre-commit + gitleaks |
| **Backups** | Proxmox Backup Server (Pi 5), Restic vers S3 (Phase ultérieure) |
| **Monitoring** | Prometheus + Grafana + Loki + Alertmanager + ntfy (Phase ultérieure) |
| **DNS public** | Cloudflare (plan free, DNS only, pas de proxy) |

---

## 5. Inventaire matériel

| Équipement | Modèle | Rôle |
|---|---|---|
| Modem fibre | LiveBox 6 Orange | Fibre 2.5G entrante. Aucun port forward, aucun DMZ, aucun UPnP. |
| Firewall | CWWK N150 fanless (6× igc) | OPNsense bare-metal |
| Switch | Netgear MS305E | 5 ports L2 VLAN-aware |
| Hyperviseur | HP Mini PC | Proxmox VE bare-metal |
| VPS public | Hetzner CX22, Debian 13 | Pangolin / Traefik / CrowdSec / portfolio / WG hub |
| Backup futur | Raspberry Pi 5 | Proxmox Backup Server (Phase ultérieure) |
| Borne WiFi future | UniFi U6 Lite | (Non commandée à ce stade) |

---

## 6. Adressage réseau

Subnet IPv4 = `10.10.X.0/24` où X = ID VLAN.

| VLAN ID | Nom | Subnet | Rôle | DHCP |
|---|---|---|---|---|
| 10 | MGMT | `10.10.10.0/24` | Administration des équipements et UIs | Oui |
| 20 | LAN | `10.10.20.0/24` | Postes utilisateurs de confiance | Oui |
| 30 | IOT | `10.10.30.0/24` | Objets connectés cloisonnés | Oui |
| 50 | EXPOSED | `10.10.50.0/24` | Services accessibles publiquement via Pangolin | IP fixes |
| 60 | SVC_PRIV | `10.10.60.0/24` | Services privés (Authentik, Vaultwarden, etc.) | IP fixes |
| 70 | LAB | `10.10.70.0/24` | Bancs d'essai isolés | IP fixes |
| 99 | BACKUP | `10.10.99.0/24` | Réseau de sauvegarde (Pi PBS futur) | Non |
| — | WG-ADMIN | `10.99.10.0/24` | Tunnel admin externe (relay via VPS) | Non |
| — | WG-PUB | `10.99.20.0/24` (TBC) | Tunnel d'exposition publique (Newt ↔ Gerbil) | Non |

---

## 7. État du déploiement actuel

À considérer comme un état hérité, à re-valider via la nouvelle doctrine
fresh-install.

| Composant | État | Re-validation requise |
|---|---|---|
| **VPS Hetzner** | Déployé via Ansible, opérationnel | Vérifier que `deploy-vps-services.yml` est joué sur un VPS vierge donne un résultat identique |
| **Portfolio public** | En ligne sur `ldesfontaine.com` | OK |
| **CrowdSec + Console** | Bouncer Traefik actif | OK |
| **WG hub admin** | En écoute UDP 51821, peers OPNsense + laptop + phone déclarés | À auditer (rotation des clés en cours, voir TODO) |
| **OPNsense** | Bare-metal, VLAN + Unbound + WG-ADMIN-CLIENT configurés via UI | Procédure de restauration XML à formaliser |
| **Proxmox** | Bare-metal, IP MGMT, repos no-subscription, bridge VLAN-aware | Rôle Ansible `proxmox-host` à formaliser |
| **Authentik LXC** | Installé (LXC sur Proxmox) | Méthode d'install à documenter, à inscrire dans le pipeline IaC |
| **Vaultwarden, Filebrowser** | Pas encore déployés | Phases ultérieures |
| **Pi5 PBS** | Pas encore branché | Phase ultérieure |
| **AP UniFi** | Non commandé | Phase ultérieure |

---

## 8. Roadmap (haut niveau, sans dates)

Les phases sont énumérées en ordre logique. Le projet n'impose pas un
ordre temporel strict — on peut paralléliser.

1. **Hygiène sécu du repo public** : audit du contenu existant, mise en
   place de `pre-commit` + `gitleaks`, chiffrement age des backups
   OPNsense déjà présents.
2. **Réorganisation du repo** : structure cible, migration des docs,
   README vitrine.
3. **Doctrine de déploiement** : `docs/deployment/{00-prerequisites,
   01-vps, 02-opnsense, 03-proxmox, 04-clients-admin}.md`.
4. **Rotation et consolidation des secrets** : clés WireGuard peers
   regénérées via procédure formelle, archivage des dossiers de clés
   éparpillés.
5. **Procédures opérationnelles** : `docs/operations/{key-rotation,
   backup-restore, disaster-recovery}.md`.
6. **Validation par test fresh-install** : déploiement complet from
   scratch en suivant la doc, sur matériel jetable ou réutilisé.
7. **Phases d'enrichissement** : Vaultwarden, Filebrowser, Authentik
   OIDC sur Pangolin, Pi5 PBS, monitoring Prometheus / Grafana / Loki,
   UniFi, etc.
8. **CI GitHub Actions** (différée — dette technique consciente) :
   workflow qui exécuterait `pre-commit run --all-files` + scan
   gitleaks complet sur push et pull request vers main. **Non mise
   en place** dans la phase initiale : la défense actuelle repose
   sur les hooks pre-commit locaux installés par `scripts/setup.sh`
   après clone, plus la discipline humaine (pas de `--no-verify`).
   Décision réversible. Déclencheurs naturels d'une mise en place
   ultérieure : ouverture du repo à des contributions externes,
   intégration d'une équipe, ou besoin de visibilité publique sur
   la validation serveur indépendante de l'état des hooks locaux du
   contributeur.

---

## 9. Mode opératoire

### 9.1 Workflow assisté

Le projet utilise une assistance IA en mode collaboratif :

- **Architect** : un assistant senior (Claude conversational) qui aide à
  réfléchir, rédiger les briefs et les prompts, reviewer les diffs avant
  commit, et tenir la cohérence avec les doctrines.
- **Implementer** : un assistant tactique (Claude Code) qui exécute les
  modifications de code à partir des prompts rédigés par l'Architect.
- **Lucas** : décideur, exécutant des playbooks Ansible, et seul
  responsable du `git push`. Garde la main sur le code.

Aucun commit n'est poussé par un assistant. Aucun trailer « Co-Authored-By »
n'est ajouté au commit message. Pratique strictement humaine.

### 9.2 Conventions de code

- **Ansible** :
  - Rôles en `snake_case`, préfixés descriptivement (`wg_admin_hub`, pas
    `wireguard`).
  - Variables en `<role>_<scope>_<name>` (`wg_admin_hub_subnet`).
  - Fichiers de playbook en `kebab-case` (`deploy-vps-services.yml`).
  - Variables de vault préfixées `vault_` strictement.
- **Python** (scripts utilitaires) :
  - Python 3, type hints, docstrings.
  - Cohérence avec l'écosystème Ansible (Jinja2 pour les templates).
- **Lint avant commit** : `ansible-lint`, `yamllint`, `python3 -m
  py_compile`.

### 9.3 Conventions de commit

- **Conventional Commits** : `feat`, `fix`, `docs`, `refactor`, `chore`,
  `revert`.
- **Granularité fine** : un changement logique = un commit.
- **Pas de trailer IA**, pas de mention « assisté par AI » dans le message.
- **Body du commit** : décrit le quoi et le pourquoi, en français.

### 9.4 Conventions de doc

- Markdown propre, en français.
- Pas de commentaires verbeux pseudo-générés qui annoncent des phases ou
  des étapes futures dans le code ou la doc. Si une étape est future,
  elle vit dans un TODO d'issue ou dans la roadmap — pas dans un
  commentaire de fichier de configuration.
- Tableaux quand il y a une structure tabulaire claire.
- Style direct, pas marketing. Privilégier « permet de », « implémente »,
  « définit ». Éviter « robuste », « puissant », « excellent ».

---

## 10. ADRs en vigueur

Les Architecture Decision Records sont sous `docs/adr/`. Liste à jour :

| ADR | Sujet | Statut |
|---|---|---|
| ADR-000 | Conventions de nommage et structure du repo | Accepté |
| ADR-001 | Stack technique initiale (Proxmox, OPNsense, Pangolin, etc.) | Accepté |
| ADR-002 | Politique de firewalling (OPNsense + UFW VPS) | Accepté |
| ADR-003 | Services *host-aware* vs *IP-friendly* (impact accès admin) | Accepté |
| ADR-004 | Invocation d'ansible-lint via hook pre-commit local | Accepté |

Tout nouveau choix structurant fait l'objet d'un ADR. Les ADRs ne sont
jamais modifiés une fois acceptés : on en écrit un nouveau qui *supersede*
l'ancien si la décision change.

---

## 11. État des secrets

| Secret | Localisation | Backup |
|---|---|---|
| Vault password Ansible | `~/.ansible/vault-pass-homelab.txt` (chmod 600) | Gestionnaire de mots de passe |
| Clé age maître | `~/.age/homelab.key` | Gestionnaire de mots de passe |
| Clés SSH homelab | `~/.ssh/id_ed25519_homelab` | Gestionnaire de mots de passe |
| Clés WireGuard peers | `~/homelab-keys/wg-admin-relay/*.key` (hors repo, chmod 600) | Archive `.tar.gz.age` sur stockage cloud chiffré |
| Backups XML OPNsense | `backups/opnsense/*.xml.age` (dans le repo, chiffrés) | Repo Git (chiffrés) + stockage cloud |
| Tokens API (Cloudflare, etc.) | `inventory/group_vars/<group>/vault.yml` (chiffré) | Dans le vault |

---

## 12. Par où commencer

### Pour un lecteur humain qui découvre le projet

1. Lire la section 2 (architecture) pour la vue d'ensemble.
2. Parcourir `docs/deployment/` pour comprendre les procédures.
3. Lire les ADRs sous `docs/adr/` pour les choix structurants.
4. Consulter les runbooks sous `docs/runbooks/` pour des cas concrets.

---

## 13. Contact

Propriétaire : Lucas Desfontaine
Domaine public : `ldesfontaine.com`
Repo : `github.com/ldesfontaine/homelab` (public)

Le repo est volontairement public à des fins de portfolio. Tous les
secrets sont chiffrés. Aucune donnée personnelle ou sensible n'est
exposée. Les pubkeys WireGuard et les FQDNs publics, en tant
qu'informations techniques publiques par nature, peuvent apparaître en
clair.
