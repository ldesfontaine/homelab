# ADR-003 — Classification des services : Host-aware vs IP-friendly, et conséquences sur la voie d'admin

> **Statut** : actif — `v1.0` — auteur `ldesfontaine`
> **Date** : 2026-05-17
> **Prérequis** : ADR-000, ADR-001, ADR-002, runbook `session-6-wireguard-hub.md` §7.2 et §12

---

## Contexte

La session 6 a déployé le hub WireGuard `wg-admin-hub` (interface `wg-admin`, réseau `10.99.10.0/24`, peers laptop + phone) pensé comme **voie d'admin distante générique** pour le homelab : depuis le tunnel, on doit pouvoir taper l'IP interne d'un service et tomber sur son UI/API d'administration sans passer par le frontal public.

Le déploiement a fonctionné côté infra (tunnel up, handshakes OK, peers correctement isolés en split-tunnel) mais a révélé une distinction architecturale **non anticipée jusque-là** : **tous les services ne sont pas accessibles de la même façon via le tunnel admin**. Cas observé sur Pangolin :

- Tentative initiale : binder `10.99.10.1:3000:3000` dans le compose pangolin pour exposer le dashboard sur l'IP du tunnel admin. Résultat : `404 Cannot GET /` sur la racine. Binding retiré (cf. commit `revert(pangolin): drop wg-admin port binding`).
- Tentative de repli : SSH tunnel `localhost:3000 → container pangolin:3000` via l'exception `AllowTcpForwarding yes` du user `deploy`. Résultat : même chose — `404`/`403` même avec un `--header "Host: pangolin.ldesfontaine.com"` forcé.

**Cause racine.** Pangolin est une application **Host-aware** : son middleware Next.js compare le `Host` header de chaque requête à la `dashboard_url` configurée (`pangolin.ldesfontaine.com`), et empile des vérifications additionnelles (origin CSRF, cookies de session liés au domaine). Toute requête qui n'arrive pas via un reverse proxy reproduisant fidèlement le `Host`, les cookies et l'origine HTTPS attendus est rejetée — quel que soit le canal réseau utilisé pour l'atteindre.

À l'inverse, OPNsense, Grafana, Vaultwarden ou un dashboard Prometheus répondent indistinctement sur n'importe quelle IP/hostname qui les joint au niveau TCP. Ils ne s'occupent pas du `Host` header pour servir leur UI d'admin.

Cette distinction est **architecturale, pas de configuration** : on ne la "fixe" pas en touchant à un flag de Pangolin, c'est un choix délibéré de leur middleware (et c'est sain — c'est une protection CSRF/clickjacking légitime). Il faut donc la prendre en compte dans la conception, pas la combattre.

## Décision

**On classifie tous les services du homelab en deux catégories, et la voie d'admin par défaut découle de la catégorie.**

### Catégorie A — Services IP-friendly

**Définition** : services dont l'UI/API d'admin répond indépendamment du `Host` header. Tapent l'IP directe ou un hostname arbitraire, ça marche.

**Exemples connus / attendus** :
- OPNsense (UI web)
- Grafana, Prometheus, Loki, Alertmanager
- Vaultwarden
- Filebrowser
- UniFi Controller
- La majorité des dashboards d'outillage interne

**Voie d'admin** : **tunnel `wg-admin`**. Le peer connecté tape l'IP interne du service (ex : `http://10.99.20.5:8080` pour Grafana sur un LXC) et accède directement à l'UI. Aucune contrainte particulière au déploiement.

### Catégorie B — Services Host-aware

**Définition** : services dont le middleware vérifie le `Host` header (et souvent l'origine CSRF + cookies liés au domaine) avant de servir la moindre page utile. Refusent toute requête qui ne correspond pas au FQDN configuré.

**Exemples connus / attendus** :
- Pangolin (confirmé session 6)
- Authentik (probable — patterns similaires des SPA modernes avec auth centralisée)
- Tout futur service basé sur Next.js / SvelteKit / Nuxt avec auth liée au domaine
- Tout service derrière son propre auth OIDC qui calcule des redirect_uri à partir du FQDN

**Voie d'admin** : **PAS via tunnel direct**. Doit vivre derrière son reverse proxy public (Pangolin → Traefik) avec `Host` matching correct, et l'accès admin se fait par le FQDN public, derrière la chaîne d'auth Authentik (OIDC), exposée publiquement mais protégée.

**Conséquence pratique** : on ne tente plus de bricoler un accès tunnel pour ces services. On les déploie correctement derrière leur reverse proxy dès le départ, et on attend la phase 11 (Authentik) pour avoir une voie d'admin sécurisée par le FQDN public.

## Conséquences

### Positives

- **Décision claire au design d'un nouveau service** : avant de déployer, on tranche A ou B, et la voie d'admin est mécaniquement décidée. Plus de boucles "essayons un binding, ah ça marche pas, essayons un SSH tunnel, ah ça marche pas non plus".
- **Le hub `wg-admin` reste utile et justifié** : il est la voie d'admin principale pour la catégorie A, qui sera probablement la majorité numérique des services du homelab (monitoring, coffres, outils internes).
- **Pas de bricolage qui finit en dette** : on n'introduit pas de SSH tunnels ou de bindings IP:port pour la catégorie B juste "en attendant". Ces solutions ne marchent pas (cf. session 6) et auraient masqué le besoin réel.
- **Cadre cohérent pour la phase 11** : Authentik n'est pas "une feature de plus", c'est **la** voie d'admin pour toute la catégorie B. Ça donne du poids à la priorité de cette phase.

### Négatives

- **La catégorie B est inaccessible jusqu'à la phase 11** : Pangolin est dans cet état aujourd'hui — aucune admin distante possible en dehors d'un accès console au VPS. Acceptable car les opérations courantes (déploiement de containers internes via Pangolin) se font par Ansible, et l'UI Pangolin reste utile mais pas critique au quotidien.
- **La classification dépend de la connaissance de chaque service** : pour un nouveau service inconnu, il faut tester avant de classer (un binding bouge un service en catégorie A si la requête revient bien, B sinon). Pas de méthode automatique. Mitigation : documenter chaque classification dans le rôle Ansible du service concerné.

## Anti-patterns à proscrire

- ❌ **Bricoler un SSH tunnel ou un binding IP:port pour un service catégorie B** "le temps que Authentik soit en place". Ça ne marche pas, ça crée de la confusion, et ça finit en commits de revert (cf. `revert(pangolin): drop wg-admin port binding`).
- ❌ **Ajouter `AllowTcpForwarding yes` au user `deploy` pour un service catégorie B** : l'exception existante (héritée de session 2 pour les tunnels admin légitimes catégorie A) ne doit pas être étendue pour justifier un workaround sur un service Host-aware.
- ❌ **Tenter de désactiver le Host check d'un service Host-aware** (ex : variable d'env Pangolin "trust all hosts") pour le rendre accessible via tunnel : casse la protection CSRF, expose l'auth à du host header injection, dette de sécurité immédiate.
- ❌ **Classer par défaut un nouveau service en catégorie A sans vérifier** : si on déploie sans tester, on découvre tard. Premier déploiement doit inclure un test "ça répond bien sur IP nue ?" avant d'écrire la doc d'admin.

## Application concrète au homelab

| Service | Catégorie | Voie d'admin |
|---|---|---|
| Pangolin (dashboard) | B (Host-aware) | Phase 11 : `pangolin.ldesfontaine.com` derrière Authentik OIDC |
| Authentik (UI admin) | B (probable, à confirmer au déploiement) | Phase 11 : `auth.ldesfontaine.com` derrière sa propre auth |
| OPNsense (UI web) | A (IP-friendly) | Tunnel `wg-admin` → IP LAN OPNsense |
| Grafana, Prometheus, Loki | A | Tunnel `wg-admin` → IP du LXC monitoring |
| Vaultwarden | A | Tunnel `wg-admin` → IP du LXC vault (UI admin, l'accès utilisateur passe par le FQDN public) |
| Filebrowser | A | Tunnel `wg-admin` → IP du LXC |
| UniFi Controller | A | Tunnel `wg-admin` → IP du LXC UniFi |

Cette table est mise à jour à chaque ajout de service.

## Statut

**Actif.** Référencé par :

- `docs/runbooks/session-6-wireguard-hub.md` §7.2 (acceptation de la limitation Pangolin)
- `docs/runbooks/session-6-wireguard-hub.md` §12 (Limites connues)
- À référencer dans le runbook de la phase 11 (Authentik) au moment de sa rédaction.
