# Runbook — Session 4 : Pangolin + bascule DNS + portfolio public

> **Statut** : actif — v1.0 — auteur `ldesfontaine`
> **Référence** : `docs/adr/ADR-001-stack-technique.md` (Pangolin), `docs/adr/ADR-002-firewall-strategy.md` (single front)
> **Playbook** : `ansible/playbooks/deploy-vps-services.yml`

Objectif de la session : déployer Pangolin (control plane Fossorial + Gerbil + Traefik) en tant qu'unique frontal HTTP/HTTPS public du VPS, basculer le portfolio en internal-only (plus aucun port host publié), émettre un certificat Let's Encrypt valide via challenge DNS-01 Cloudflare, et basculer le DNS de l'apex et du sous-domaine `portfolio.ldesfontaine.com` pour rendre le site publiquement accessible.

À la fin de la session : `https://portfolio.ldesfontaine.com` répond en HTTP/2 200 avec un certificat Let's Encrypt valide, l'apex `https://ldesfontaine.com` redirige en 301 vers le portfolio, et `nmap` depuis l'extérieur ne montre que `2203/tcp` (SSH), `80/tcp` et `443/tcp`.

---

## 1. Prérequis

- Sessions 1 (bootstrap), 2 (hardening), 3 (Docker + portfolio internal localhost) jouées avec succès. Idempotence prouvée : un re-run de chaque playbook renvoie `changed=0`.
- `ssh -p 2203 deploy@<ip>` fonctionne, `sudo` NOPASSWD configuré.
- Image `ghcr.io/ldesfontaine/portfolio:0.0.4` (ou tag plus récent) publiée et publique sur GHCR.
- **Vault** :
  - `vault_portfolio_payload_secret` : valeur réelle (session 3).
  - `vault_pangolin_admin_password` : valeur réelle (mot de passe fort, ≥ 24 caractères). Si encore en placeholder, regénérer : `openssl rand -base64 24` puis `ansible-vault edit ansible/inventory/group_vars/vps/vault.yml`.
  - `vault_cloudflare_api_token` : token Cloudflare réel, scope **`Zone:DNS:Edit` sur la zone `ldesfontaine.com` uniquement** (pas un token global). Le template ACME utilisera ce token pour passer le DNS-01 challenge.
- **Compte Cloudflare** : zone `ldesfontaine.com` active, accès admin disponible (pour la bascule DNS en phase B).
- `ssh-agent` chargé avec `~/.ssh/id_ed25519_homelab`.
- Mot de passe vault en place : `~/.ansible/vault-pass-homelab.txt` lisible.
- Console KVM Hetzner accessible (voie de récupération si UFW casse le réseau).
- Collections installées :

  ```bash
  cd ansible
  ansible-galaxy collection install -r requirements.yml
  ```

  En particulier `community.docker` ≥ 3.10.0 (pour `docker_compose_v2` et `docker_container_exec`) et `community.general` ≥ 8.0.0 (pour `ufw` avec `route`).

---

## 2. Validation pré-vol (sans toucher au VPS)

### 2.1. Vérifier les versions épinglées dans `roles/pangolin/defaults/main.yml`

Trois versions à confronter aux dernières releases stables upstream :

```bash
# Pangolin
curl -s https://api.github.com/repos/fosrl/pangolin/releases/latest | jq -r .tag_name
# Gerbil
curl -s https://api.github.com/repos/fosrl/gerbil/releases/latest  | jq -r .tag_name
# Traefik — on suit la mineure validée par Pangolin upstream (v3.6 actuellement)
```

Si les valeurs `pangolin_version`, `pangolin_gerbil_version`, `pangolin_traefik_version` ne correspondent pas, soit on accepte le delta (releases majeures parfois cassantes — lire le changelog Pangolin avant), soit on bump les valeurs avant le run.

### 2.2. Confirmer que les secrets vault ne sont pas restés en placeholder

```bash
cd ansible
ansible -m debug -a 'var=pangolin_cloudflare_api_token' vps-pangolin
ansible -m debug -a 'var=pangolin_admin_password' vps-pangolin
```

Les deux doivent retourner une valeur — pas la chaîne litérale `{{ vault_... }}`, pas `VARIABLE IS NOT DEFINED`, et idéalement pas une valeur trop courte ou évidente. Ces commandes affichent les secrets en clair dans le terminal — fermer l'historique shell ensuite (`history -c`).

### 2.3. Vérifier la validité du token Cloudflare avant le run

```bash
TOKEN=$(ansible -m debug -a 'var=pangolin_cloudflare_api_token' vps-pangolin \
        --one-line 2>/dev/null | sed 's/.*=> //; s/.*"pangolin_cloudflare_api_token": "//; s/".*//')
curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.cloudflare.com/client/v4/user/tokens/verify | jq .
unset TOKEN
```

Le JSON renvoyé doit avoir `"status": "active"`. Si l'API répond `Invalid API token` → recréer le token côté Cloudflare avec le bon scope avant de lancer Ansible.

### 2.4. Syntaxe + lint + dry-run

```bash
cd ansible
ansible-playbook playbooks/deploy-vps-services.yml --syntax-check
ansible-lint
yamllint -c ../.yamllint .

# Dry-run (n'écrit rien sur le VPS mais lit l'état actuel)
ansible-playbook playbooks/deploy-vps-services.yml --check --diff --tags pangolin
```

### 2.5. Snapshot des records DNS Cloudflare actuels (utile pour rollback)

```bash
dig +short ldesfontaine.com           A
dig +short ldesfontaine.com           AAAA
dig +short portfolio.ldesfontaine.com A
dig +short portfolio.ldesfontaine.com AAAA
dig +short pangolin.ldesfontaine.com  A
```

Sauvegarder la sortie dans un gist privé / fichier local : c'est ce qu'on remet en place si on rollback la bascule DNS.

---

## 3. Procédure d'exécution

La session se déroule en **deux phases distinctes** : Phase A déploie le frontal sans toucher au DNS (rien n'est encore public). Phase B bascule le DNS Cloudflare et rend le site joignable. Cette séparation permet de valider Pangolin et l'émission du cert en isolation avant d'exposer publiquement.

### Phase A — Déploiement frontal (DNS encore inchangé)

#### 3.A.1. Run réel

```bash
cd ansible
ansible-playbook playbooks/deploy-vps-services.yml
```

Effets attendus :

- Le réseau Docker `pangolin-net` est créé (rôle `pangolin` → `prep.yml`).
- Les images `fosrl/pangolin:1.x.x`, `fosrl/gerbil:1.x.x`, `traefik:v3.6` sont pulled.
- Le compose `/opt/pangolin/docker-compose.yml` démarre 3 containers : `pangolin`, `gerbil`, `traefik`.
- `acme.json` (0600) est créé sous `/opt/pangolin/config/letsencrypt/`.
- UFW reçoit deux règles `ufw route allow proto tcp port 80` et `... port 443` dans la chaîne `ufw-user-forward` (cf. `tasks/ufw-allow.yml`).
- Le rôle `portfolio` redéploie le container portfolio **sans** mapping de port host (`portfolio_bind_localhost: false` est désormais le défaut) et le rattache à `pangolin-net`.
- Le wait HTTP du rôle portfolio passe désormais par `docker exec wget` interne (pas via 127.0.0.1:3000).

Le run doit terminer en ~3-5 min sur une connexion correcte. Si Pangolin met longtemps à devenir healthy (sa healthcheck est sur l'API interne :3001), le `retries: 30, delay: 5` du rôle laisse jusqu'à 2 min 30 — au-delà, lire les logs (§5.1).

#### 3.A.2. Vérifications côté VPS (Pangolin healthy, certs en cours)

```bash
ssh -p 2203 deploy@<ip-vps>

# Containers Up
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
# Doit lister : pangolin (Up, healthy), gerbil (Up, ports 80,443,51820/udp,21820/udp),
#               traefik (Up, ports affichés via gerbil — net=service:gerbil),
#               portfolio (Up, AUCUN port).

# Pangolin API répond en interne
docker exec pangolin curl -sf http://127.0.0.1:3001/api/v1/

# Traefik a obtenu (ou est en train d'obtenir) un cert Let's Encrypt via DNS-01
docker logs traefik 2>&1 | grep -iE 'acme|certificate|cloudflare' | tail -30
# Doit montrer : "Starting provider *traefik/v3/pkg/provider/acme/Provider", puis
#                 "Building ACME client", puis "Certificate obtained" pour chaque domaine.

# Cert effectivement écrit sur disque
sudo jq 'keys' /opt/pangolin/config/letsencrypt/acme.json
# Doit retourner ["cloudflare"]
sudo jq '.cloudflare.Certificates[].domain' /opt/pangolin/config/letsencrypt/acme.json
# Doit lister portfolio.ldesfontaine.com, ldesfontaine.com, pangolin.ldesfontaine.com
# (les hostnames déclarés dans pangolin_routes + le dashboard Pangolin).
```

#### 3.A.3. Validation TLS sans bascule DNS (via `--resolve`)

```bash
# Depuis le laptop, simuler une résolution DNS qui pointerait déjà vers le VPS :
curl -v --resolve portfolio.ldesfontaine.com:443:<ip-vps> \
  https://portfolio.ldesfontaine.com/ 2>&1 | grep -E 'HTTP|subject|issuer|expire'
```

Sortie attendue :
- `HTTP/2 200`
- `subject: CN=portfolio.ldesfontaine.com`
- `issuer: ...Let's Encrypt...` (pas `TRAEFIK DEFAULT CERT` ; si c'est ce dernier, le challenge ACME a échoué → §5)
- Corps de la réponse = HTML du portfolio

Tester aussi l'apex :
```bash
curl -v --resolve ldesfontaine.com:443:<ip-vps> https://ldesfontaine.com/ 2>&1 | head -30
# Doit renvoyer 301 → https://portfolio.ldesfontaine.com/
```

Si tout est vert ici : on peut basculer le DNS. Si rouge : pas de bascule DNS tant que ce n'est pas vert (§5 rollback).

### Phase B — Bascule DNS Cloudflare (manuelle, dashboard)

Cette phase n'est PAS automatisée par Ansible (cf. périmètre session 4). L'admin opère directement sur le dashboard Cloudflare.

#### 3.B.1. Préparation

- Onglet Cloudflare → `ldesfontaine.com` → `DNS` → `Records`.
- Récupérer l'IPv4 du VPS : `dig <ip-vps>` ou console Hetzner (champ "IP").
- Récupérer l'IPv6 du VPS si présente (Hetzner alloue par défaut un /64).

#### 3.B.2. Créer / éditer les records (TTL court pour la bascule)

| Type | Name | Content | Proxy | TTL |
|---|---|---|---|---|
| A | `@` (apex) | `<ip-vps>` | **DNS only** (gris) | `Auto` (5 min Cloudflare géré) |
| AAAA | `@` (apex) | `<ipv6-vps>` | DNS only | Auto |
| A | `portfolio` | `<ip-vps>` | DNS only | Auto |
| AAAA | `portfolio` | `<ipv6-vps>` | DNS only | Auto |
| A | `pangolin` | `<ip-vps>` | DNS only | Auto |
| AAAA | `pangolin` | `<ipv6-vps>` | DNS only | Auto |

**Pourquoi DNS only et pas "proxied" (orange cloud)** :

1. Le proxy Cloudflare réécrit l'IP source visible côté Traefik (X-Forwarded-For) ; nos logs et CrowdSec (session 5) deviennent moins lisibles.
2. Le challenge DNS-01 Cloudflare ne dépend pas du proxying, mais en mode "proxied" Cloudflare termine TLS lui-même → notre cert Let's Encrypt côté Traefik n'est plus utilisé pour le client final, et on perd le contrôle.
3. Le port 80 HTTP→HTTPS redirect côté Traefik est court-circuité par Cloudflare en mode proxied → comportement moins prévisible.

Décision projet : **toujours DNS only** sur cette zone tant qu'on a Pangolin en frontal.

#### 3.B.3. Attendre la propagation

```bash
# Depuis le laptop (pas via /etc/hosts) :
dig +short portfolio.ldesfontaine.com
dig +short ldesfontaine.com
dig +short pangolin.ldesfontaine.com
```

Doivent toutes retourner `<ip-vps>`. Compter 1-5 min selon le TTL précédent (s'il y avait des records). Si on ne voit pas la nouvelle IP après 10 min : vérifier que les anciens records ont bien été supprimés/édités (pas juste un nouveau créé en parallèle).

#### 3.B.4. Test public end-to-end

```bash
# Sans --resolve, depuis n'importe quel réseau hors VPS :
curl -I https://portfolio.ldesfontaine.com/
# HTTP/2 200, cert Let's Encrypt

curl -I http://portfolio.ldesfontaine.com/
# HTTP/1.1 308 → redirection vers https://

curl -I http://ldesfontaine.com/
# HTTP/1.1 308 (Traefik HTTPS redirect) puis HTTP/2 301 → https://portfolio.ldesfontaine.com/
```

Tester depuis 4G / un autre réseau pour confirmer l'accès public (pas un cache DNS local trompeur).

---

## 4. Post-cutover validation

### 4.1. Cert Let's Encrypt valide

```bash
openssl s_client -connect portfolio.ldesfontaine.com:443 -servername portfolio.ldesfontaine.com \
  < /dev/null 2>&1 | openssl x509 -noout -dates -issuer -subject
```

Attendu :
- `issuer=C=US, O=Let's Encrypt, CN=R3` (ou R10/R11 selon l'année).
- `subject=CN=portfolio.ldesfontaine.com`
- `notAfter=` dans ~89 jours.

### 4.2. Tous les containers Up

```bash
ssh -p 2203 deploy@<ip-vps> 'docker ps --format "table {{.Names}}\t{{.Status}}"'
```

Attendu : 4 lignes, toutes `Up`, pangolin marqué `(healthy)`.

### 4.3. Surface réseau publique limitée

Depuis le laptop (hors VPS) :

```bash
nmap -p 1-1024 <ip-vps>
```

Attendu : seulement `80/tcp open`, `443/tcp open`, `2203/tcp filtered|open` (ssh sur port non standard).
**Rien d'autre.** Si on voit `51820/udp` ouvert publiquement → Gerbil expose les ports WG, mais UFW ne devrait PAS les avoir ouverts (cf. `tasks/ufw-allow.yml` qui ne touche pas à l'UDP). Vérifier `sudo ufw status verbose` côté VPS.

```bash
# Côté VPS, vue host de ce qui écoute :
sudo ss -tlnp | grep -v '127.0.0.1\|::1'
sudo ss -ulnp | grep -v '127.0.0.1\|::1'
```

Doit montrer seulement :
- `:::80` → docker-proxy (gerbil)
- `:::443` → docker-proxy (gerbil)
- `:::2203` → sshd
- `:::51820/udp` et `:::21820/udp` → docker-proxy (gerbil) — ouvert côté host, **bloqué côté UFW** (cf. §4.4).

### 4.4. UFW route status

```bash
sudo ufw status verbose
```

Sections à vérifier :
- `Default: deny (incoming), allow (outgoing), deny (routed)` ← le `deny (routed)` est important.
- Section `Anywhere on FORWARD` doit lister `80/tcp ALLOW FWD Anywhere` et `443/tcp ALLOW FWD Anywhere` (les deux règles `ufw route allow` posées par le rôle pangolin).
- Pas de règle `51820/udp` (Newt désactivé pour cette session).

### 4.5. Idempotence

```bash
cd ansible
ansible-playbook playbooks/deploy-vps-services.yml
# Doit afficher PLAY RECAP avec changed=0 (rerun à blanc).
```

Si changed > 0 sur le rôle pangolin sans qu'on ait modifié les templates → relire le diff sur les fichiers concernés (probablement formatage Jinja qui ne survit pas au rerun).

### 4.6. Renouvellement Let's Encrypt — vérification de la chaîne d'auto-renouvellement

Traefik renouvelle automatiquement les certs ~30 jours avant expiration. Pour vérifier que la chaîne est armée :

```bash
ssh -p 2203 deploy@<ip-vps>
docker logs traefik 2>&1 | grep -iE 'renew|certificate' | tail -10
```

À noter pour le futur : monitorer la date d'expiration via Grafana (session 7+).

---

## 5. Rollback

### 5.1. Émission cert Let's Encrypt échoue (DNS-01)

Symptômes : Phase A passe Pangolin healthy mais `curl --resolve ... https://...` retourne un cert "TRAEFIK DEFAULT CERT" (auto-signé) au lieu du Let's Encrypt.

Diagnostic :

```bash
docker logs traefik 2>&1 | grep -iE 'acme|cloudflare|error' | tail -40
```

Causes courantes :
- **Token Cloudflare invalide ou scope insuffisant** : message `unable to find a satisfactory authoritative ...` ou `authentication failed`. Recréer le token, mettre à jour le vault, rejouer `--tags pangolin`.
- **Rate-limit Let's Encrypt prod** : on est trop souvent passé en prod en testant. Bascule en staging :
  ```bash
  ansible-playbook playbooks/deploy-vps-services.yml --tags pangolin \
    -e pangolin_letsencrypt_ca_server=https://acme-staging-v02.api.letsencrypt.org/directory
  ```
  Une fois la chaîne validée en staging (le cert est marqué "Let's Encrypt staging"), supprimer `/opt/pangolin/config/letsencrypt/acme.json`, repasser en prod et rejouer.
- **Cloudflare propage lentement le record TXT** : Traefik fait plusieurs tentatives, attendre 2-3 min. Si persiste : vérifier que la zone est bien `ldesfontaine.com` et que le token a `Zone:DNS:Edit` sur cette zone précise.

### 5.2. Pangolin ne démarre pas (container restart loop)

```bash
docker logs pangolin --tail 100
docker logs gerbil  --tail 50
```

Hypothèses :
- `config/config.yml` invalide (YAML mal formé après edition manuelle) → restaurer le `.backup` créé par Ansible (`ls /opt/pangolin/config/config.yml*`).
- `server.secret` vide ou trop court → vérifier `pangolin_server_secret` côté vault.
- Conflits de port 80/443 avec un autre service déjà bindé sur l'host → `sudo ss -tlnp | grep -E ':80 |:443 '` (devrait être uniquement docker-proxy/gerbil).

Workflow :
```bash
ssh -p 2203 deploy@<ip-vps>
cd /opt/pangolin
sudo docker compose down
# corriger l'erreur de conf (édition vault + rejouer Ansible, PAS d'édition à la main sur le VPS)
```

### 5.3. Rollback complet vers session 3 (portfolio en localhost)

Si on veut revenir à l'état post-session 3 (portfolio sur 127.0.0.1:3000, pas de Pangolin) :

```bash
# Côté VPS : stopper la stack pangolin
ssh -p 2203 deploy@<ip-vps>
sudo docker compose -f /opt/pangolin/docker-compose.yml down
sudo systemctl is-active docker   # rester actif

# Côté pilotage : rejouer le rôle portfolio en bind localhost
cd ansible
ansible-playbook playbooks/deploy-vps-services.yml \
  --tags portfolio \
  -e portfolio_bind_localhost=true
```

Côté DNS : remettre les records Cloudflare à leur état pré-bascule (cf. §2.5 snapshot). Le site cesse d'être public.

Note : `ufw route allow 80/tcp` et `443/tcp` restent en place après le rollback. Inoffensif sans container qui publie ces ports. Pour les retirer aussi :

```bash
ssh -p 2203 deploy@<ip-vps>
sudo ufw route delete allow proto tcp from any to any port 80
sudo ufw route delete allow proto tcp from any to any port 443
```

### 5.4. Bascule DNS faite mais site KO en prod

Le rollback DNS est le plus rapide :

1. Cloudflare → DNS → remettre les records à leur état pré-bascule (cf. §2.5).
2. TTL court (Auto = 5 min Cloudflare) → propagation rapide.
3. Investiguer côté VPS sans pression (rien n'est public le temps que le DNS revienne).

---

## 6. Limites connues — reportées aux sessions suivantes

- **Pas de CrowdSec** : Pangolin/Traefik est exposé "nu" à internet. Quelques scans bots vont apparaître dans `docker logs traefik`. Acceptable pour 1-2 semaines, à durcir en **session 5** (CrowdSec bouncer dans la chaîne middleware Traefik).
- **Pas de Newt/Gerbil tunnel** : Gerbil est déployé et écoute en UDP 51820/21820, mais aucun agent Newt n'est connecté et UFW bloque ces ports. L'activation viendra avec le déploiement OPNsense/homelab (futur).
- **Pas de WireGuard hub admin** : pas encore d'accès admin distant via VPN. Pour l'instant : SSH sur 2203 directement. Session 6.
- **Pangolin dashboard exposé publiquement** sur `https://pangolin.ldesfontaine.com` : protégé par auth Pangolin (badger middleware + login admin), mais surface publique. Acceptable tant que l'admin est l'unique utilisateur ; revoir en session 5+ (potentiellement le mettre derrière WG admin uniquement).
- **Routes IaC vs UI Pangolin** : le portfolio et l'apex sont déclarés statiquement dans `roles/pangolin/templates/dynamic_config.yml.j2`. Pangolin offre aussi une UI pour gérer des "resources" — non utilisée en session 4 pour rester full-IaC. À reconsidérer si on multiplie les services exposés et que la friction Ansible devient gênante.
- **Renouvellement Let's Encrypt** : automatique côté Traefik (~30j avant expiration). Pas de monitoring/alerting actif pour le moment — à câbler sur Grafana en session 7+.
- **Sauvegarde Pangolin** : `/opt/pangolin/config/` contient toute la donnée (Pangolin DB + acme.json). Aucun backup automatisé en session 4 — la stratégie PBS arrivera plus tard.

---

## 7. Journal d'exécution

| Date | Opérateur | Phase A `changed=` | Phase B faite ? | Cert Let's Encrypt OK ? | Notes |
|---|---|---|---|---|---|
|  |  |  |  |  |  |
