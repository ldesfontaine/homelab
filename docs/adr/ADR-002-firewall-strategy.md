# ADR-002 — Stratégie firewall : portabilité et défense en profondeur sans cloud-provider lock-in

> **Statut** : actif — `v1.0` — auteur `ldesfontaine`
> **Date** : 2026-05-16
> **Prérequis** : ADR-000, ADR-001, cahier des charges section 16

---

## Contexte

Docker manipule directement `iptables` (chaînes `DOCKER` et `DOCKER-USER`) **avant** que UFW ne voie le trafic. Conséquence connue : un `docker run -p 8080:80 nginx` rend le port 8080 publiquement accessible **même si UFW a une règle `deny 8080`**. Ce comportement est documenté côté Docker comme étant *by design* (nécessaire au NAT pour les containers) — ce n'est pas un bug.

Le homelab `ldesfontaine.com` va déployer plusieurs containers Docker sur le VPS Hetzner dès la session 3 (Pangolin, portfolio, CrowdSec bouncer, etc.). Une stratégie firewall doit être arrêtée **avant** d'installer Docker.

Trois options envisagées :

| Option | Description | Avantage | Inconvénient bloquant |
|---|---|---|---|
| A — Cloud firewall Hetzner | Filtrer en amont chez Hetzner Cloud (couche provider) | Bypass Docker non pertinent (le trafic n'arrive même pas) | **Lock-in fournisseur** : si on migre vers OVH/Scaleway/autres, on doit tout reconfigurer manuellement |
| B — `iptables: false` Docker | Désactive complètement la gestion iptables par Docker | UFW reprend le contrôle total | Casse le routing inter-containers et le port forwarding. Implique de réécrire à la main toutes les règles NAT — non maintenable. |
| C — Architecture "internal-only" + `chaifeng/ufw-docker` | Containers internes sans `ports:` mappé sur l'host + script communautaire qui intègre UFW dans la chaîne `DOCKER-USER` | **Portable** d'un fournisseur à l'autre. UFW reste source de vérité. | Dépendance à un projet communautaire (mais largement adopté en 2025-2026, maintenu, code court et auditable) |

## Décision

**Option C** retenue : pas de cloud firewall, défense en deux couches portables.

### Couche 1 — Architecture (la défense principale)

**Tous les containers internes** (portfolio, CrowdSec bouncer, agents, etc.) :
- N'utilisent **AUCUN** `ports:` mappé sur l'host
- Sont sur des réseaux Docker dédiés (`pangolin-net` ou équivalent)
- Sont joignables uniquement via le DNS Docker interne, depuis d'autres containers du même réseau

**Seul** le container Pangolin (Traefik intégré) expose des ports sur l'host :
- `80/tcp` (HTTP)
- `443/tcp` (HTTPS)

**Container WireGuard** (hors Docker, géré nativement sur l'host par le rôle `wg-admin-hub` — cf. cahier) :
- `51820/udp` (WG public — Newt tunnel vers OPNsense)
- `51821/udp` (WG admin — accès distant ldesfontaine)

### Couche 2 — `chaifeng/ufw-docker` (le filet de sécurité)

Le script `ufw-docker` (https://github.com/chaifeng/ufw-docker) ajoute dans `/etc/ufw/after.rules` une intégration dans la chaîne `DOCKER-USER`. Cette chaîne est **garantie** par Docker comme un point d'extension utilisateur que Docker ne touche jamais.

**Effet** :
- Tout port publié par Docker est **bloqué par défaut**, même si l'admin (ou un futur container par erreur) ajoute un `-p 8080:80`
- L'autorisation se fait via `sudo ufw-docker allow <container> <port>` (équivalent UFW pour les containers)

**Justification du choix de `chaifeng/ufw-docker`** :
- Projet le plus largement adopté pour ce cas en 2025-2026 (consensus articles tech, documentation Docker se réfère à la chaîne `DOCKER-USER` mais ne fournit pas l'intégration UFW elle-même)
- Maintenu, code court (~200 lignes shell, auditable)
- Mode "Docker Swarm-aware" (non utilisé chez nous, mais signe de maturité)
- Compatible Debian Trixie 13 (nftables via iptables-nft, validé par les articles 2026)

### Pinning de version

Le script `ufw-docker` est référencé par **tag de release Git** dans le rôle Ansible, pas par `latest`. Le rôle Ansible vérifie le checksum SHA256 du script à chaque run pour détecter toute altération upstream.

## Ports publics autorisés sur le VPS (état cible)

| Port | Protocol | Service | Source |
|---|---|---|---|
| 2203 | TCP | SSH (deploy@) | UFW classique (rôle `bootstrap`) |
| 80 | TCP | HTTP → redirect HTTPS (Pangolin) | `ufw-docker allow pangolin-traefik 80` |
| 443 | TCP | HTTPS (Pangolin) | `ufw-docker allow pangolin-traefik 443` |
| 51820 | UDP | WireGuard public (Newt tunnel) | UFW classique (service hôte, hors Docker) |
| 51821 | UDP | WireGuard admin (accès ldesfontaine) | UFW classique (service hôte, hors Docker) |

Tout le reste est **default deny**.

## Conséquences

### Positives

- **Portabilité totale** : on change de fournisseur, on rejoue Ansible, tout marche. Pas de console fournisseur à reconfigurer.
- **Défense en profondeur** : architecture + filet de sécurité. Une erreur humaine (typo dans un compose) est rattrapée par `ufw-docker`.
- **UFW reste source de vérité** : pas de double gestion (cloud + host).
- **Lisibilité** : un seul endroit pour comprendre ce qui est exposé : `ufw status verbose` sur le VPS.

### Négatives

- **Dépendance projet tiers** : `chaifeng/ufw-docker` doit rester maintenu. Mitigation : on pin une version, on a une copie du script dans `roles/<nom>/files/`, on peut le fork si besoin.
- **Chaîne mentale plus complexe** : il faut comprendre `DOCKER-USER` quand on debug un problème réseau. Mitigation : documenté dans `docs/runbooks/`.

## Anti-patterns à proscrire (pour Claude Code et futurs contributeurs)

- ❌ **`ports: ["8080:80"]`** dans un compose de container interne (au-delà de Pangolin) : doit être remplacé par `expose:` ou suppression complète, avec accès via le réseau Docker uniquement
- ❌ **Activer le firewall Hetzner Cloud** (lock-in fournisseur)
- ❌ **`iptables: false` dans `daemon.json`** (casse Docker)
- ❌ **`ufw allow 8080`** pour autoriser un port Docker (ne marche pas — Docker bypasse UFW). Doit utiliser `ufw-docker allow <container> <port>`
- ❌ **Binding `0.0.0.0` explicite** dans un compose (`-p 0.0.0.0:8080:80`) : équivalent à `ports: ["8080:80"]`, même problème
- ❌ Ajouter un container avec `network_mode: host` "pour aller plus vite" : contourne toute la défense

## Vérification opérationnelle

À chaque déploiement de nouveau container, vérifier après le run :

```bash
# 1. Quels ports sont effectivement bindés sur l'host ?
sudo ss -tlnp | grep -v '127.0.0.1\|::1'

# 2. Vue UFW classique + DOCKER-USER
sudo ufw status verbose

# 3. Tester depuis l'extérieur (depuis le laptop, pas le VPS)
nmap -p 1-65535 <ip-vps>
# Doit montrer uniquement les ports listés dans le tableau "Ports publics autorisés" ci-dessus
```

Cette vérification est intégrée au runbook de chaque session qui touche au réseau (sessions 3, 4, 5).

---

## Changelog

| Date | Version | Changement |
|---|---|---|
| 2026-05-16 | 1.0 | Création initiale — stratégie firewall portable, retenue Option C |
