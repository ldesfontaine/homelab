# Runbook — Session 5 : CrowdSec agent + bouncer Traefik

> **Statut** : actif — v1.0 — auteur `ldesfontaine`
> **Référence** : `docs/adr/ADR-001-stack-technique.md` (CrowdSec dans la stack), `docs/adr/ADR-002-firewall-strategy.md` (agent internal-only sur pangolin-net)
> **Playbook** : `ansible/playbooks/deploy-vps-services.yml`
> **Rôles touchés** : `pangolin` (templates Traefik patchés), `crowdsec` (nouveau)

Objectif de la session : greffer CrowdSec sur le frontal Pangolin/Traefik déployé en session 4. Concrètement : (a) faire passer les logs Traefik en format JSON pour qu'ils soient parsables, (b) charger le plugin Traefik `crowdsec-bouncer-traefik-plugin` à côté de `badger`, (c) déployer un agent CrowdSec en Docker sur `pangolin-net` (LAPI :8080, aucun port host), (d) attacher le middleware bouncer à toutes les routes backend du file provider Traefik (`portfolio-router` aujourd'hui), (e) verrouiller une politique d'escalation par bans (pas de captcha — décision projet), (f) permettre un enrôlement futur à la CrowdSec Console sans modifier le code.

À la fin de la session : un scan de `https://portfolio.ldesfontaine.com/.env` répété déclenche un ban dans `cscli decisions list`, les requêtes suivantes depuis l'IP source basculent en `403`, et `nmap` depuis l'extérieur ne montre toujours que `2203/tcp`, `80/tcp`, `443/tcp` (CrowdSec n'expose AUCUN port public — ADR-002).

---

## 1. Prérequis

- Sessions 1 → 4 jouées avec succès. `https://portfolio.ldesfontaine.com` répond en HTTP/2 200, cert Let's Encrypt valide. Idempotence prouvée (re-run = `changed=0`).
- `ssh -p 2203 deploy@<ip-vps>` fonctionne, `sudo` NOPASSWD configuré.
- `ssh-agent` chargé avec `~/.ssh/id_ed25519_homelab`, mot de passe vault dispo (`~/.ansible/vault-pass-homelab.txt`).
- Collections Ansible à jour :

  ```bash
  cd ansible
  ansible-galaxy collection install -r requirements.yml
  ```

  En particulier `community.docker` ≥ 3.10.0 (pour `docker_compose_v2`, `docker_container_exec`, `docker_network_info`).

### 1.1. Génération de la clé bouncer

La clé partagée entre l'agent CrowdSec et le plugin Traefik est créée hors Ansible (32 octets aléatoires, hex) :

```bash
openssl rand -hex 32
```

Conserver la valeur pour l'ajouter au vault dans 1.2.

### 1.2. Édition du vault VPS

```bash
ansible-vault edit ansible/inventory/group_vars/vps/vault.yml
```

Ajouter les trois variables suivantes. La clé d'enrôlement Console reste vide tant qu'on ne s'enrôle pas (cf. §6). L'email Let's Encrypt sort du repo public dans la même passe — LE l'utilise comme dernier recours d'alerte en cas d'échec de renouvellement (~20j avant expiration), c'est la corde de rappel avant un black-out cert ; on veut une boîte que Lucas relève réellement, et pas en clair dans `vars.yml` (scraping spam garanti sur un repo public).

```yaml
# Clé partagée bouncer Traefik ↔ agent CrowdSec.
# Générée via `openssl rand -hex 32` — 32 octets hex obligatoires côté bouncer.
vault_crowdsec_bouncer_key: "<sortie de openssl rand -hex 32>"

# Clé d'enrôlement CrowdSec Console (app.crowdsec.net).
# Laisser vide tant qu'on ne veut pas pousser l'agent dans la Console
# (DISABLE_ONLINE_API sera positionné à `true` dans ce cas, pas de CTI).
vault_crowdsec_enroll_key: ""

# Email de contact ACME — Let's Encrypt s'en sert UNIQUEMENT pour alerter
# en cas d'échec de renouvellement. Mettre une vraie boîte (Gmail perso, etc.)
# — la valeur "lucas@ldesfontaine.com" précédente ne sert à rien sans MX
# records derrière, donc un black-out cert ne serait pas notifié.
vault_letsencrypt_email: "<ton-vrai-gmail@gmail.com>"
```

> **Note** : `vault_letsencrypt_email` est désormais référencé dans `roles/pangolin/defaults/main.yml` (`pangolin_letsencrypt_email`). Le re-run du rôle pangolin **plantera tôt** avec `'vault_letsencrypt_email' is undefined` si la variable n'est pas posée — c'est volontaire (fail fast).

### 1.3. Validation pré-vol

```bash
cd ansible

# 1. Le bouncer key est bien chargée
ansible -m debug -a 'var=crowdsec_bouncer_key' vps
# La valeur doit s'afficher en clair (no_log n'agit qu'au runtime du playbook).

# 2. Versions pinnées cohérentes
ansible -m debug -a 'var=crowdsec_image_tag' vps
ansible -m debug -a 'var=pangolin_traefik_plugin_crowdsec_version' vps

# 3. Syntaxe + lint + dry-run
ansible-playbook playbooks/deploy-vps-services.yml --syntax-check
ansible-lint roles/crowdsec
yamllint -c ../.yamllint roles/crowdsec
ansible-playbook playbooks/deploy-vps-services.yml \
  --check --diff --tags pangolin,crowdsec
```

Fermer l'historique shell après avoir affiché le bouncer key (`history -c`) si l'environnement est partagé.

---

## 2. Exécution

```bash
cd ansible
ansible-playbook -i inventory/00-static.yml playbooks/deploy-vps-services.yml \
  --tags pangolin,crowdsec --diff
```

Effets attendus :

- **Rôle pangolin** :
  - Template `traefik_config.yml` réécrit (accessLog → JSON + plugin `crowdsec-bouncer` à côté de `badger`). Le handler `Restarting traefik` est déclenché (Traefik bascule en restart pour relire la conf statique).
  - Template `dynamic_config.yml` réécrit (middleware `crowdsec-bouncer` défini + attaché à `portfolio-router`). Pas de restart — file provider en `watch: true`.
- **Rôle crowdsec** :
  - `/opt/crowdsec/{config,data}` créés (0700 root).
  - Image `crowdsecurity/crowdsec:v1.7.8` pull.
  - Container `crowdsec` up sur `pangolin-net`, AUCUN port host. L'entrypoint upstream copie ses configs par défaut dans `/etc/crowdsec/` et installe les collections (`COLLECTIONS` env).
  - Wait : présence du marqueur `/opt/crowdsec/config/config.yaml` (seed terminé) puis `cscli lapi status` OK.
  - `acquis.yaml` et `profiles.yaml` overlayés sur l'host → handler `Reloading crowdsec` (SIGHUP, pas de coupure).
  - `cscli bouncers add traefik-bouncer --key <vault>` (idempotent — skip si déjà présent).
  - Enrôlement Console SKIP (la clé vault est vide).

Premier run : `changed > 0` côté pangolin (templates patchés) ET côté crowdsec (déploiement initial). Deuxième run consécutif : `changed=0` sur les deux rôles.

---

## 3. Vérifications fonctionnelles

Depuis le VPS (`ssh -p 2203 deploy@<ip-vps>`) :

### 3.1. Container et image

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Networks}}' | grep -E 'crowdsec|traefik'
```

Attendu : `crowdsec  Up (healthy)  pangolin-net` ; `traefik  Up (healthy)` (network_mode service:gerbil — pas de "pangolin-net" affiché côté traefik mais c'est bien sur le même netns).

```bash
docker image inspect crowdsecurity/crowdsec:v1.7.8 --format '{{.RepoDigests}}'
```

### 3.2. Métriques CrowdSec — parsers actifs

```bash
docker exec crowdsec cscli metrics
```

Attendu (extrait) :
- Section `Acquisition Metrics` : `/var/log/traefik/access.log` avec `lines parsed > 0`, `lines unparsed = 0` (ou très peu).
- Section `Parser Metrics` : `crowdsecurity/traefik-logs` avec `hits > 0`, `parsed > 0`.
- Section `Scenario Metrics` : initialement vide tant qu'aucune alerte ne s'est déclenchée.

### 3.3. Collections présentes

```bash
docker exec crowdsec cscli collections list -o human
```

Attendu : `crowdsecurity/traefik`, `crowdsecurity/base-http-scenarios`, `crowdsecurity/sshd`, `crowdsecurity/linux` toutes en `status: enabled`.

### 3.4. Bouncer Traefik enregistré et joignable

```bash
docker exec crowdsec cscli bouncers list -o human
```

Attendu : ligne `traefik-bouncer` avec `valid: ✔` et `last_pull` < 1 min (le plugin Traefik fait son premier pull au démarrage en mode stream).

```bash
docker logs traefik 2>&1 | grep -iE 'crowdsec|bouncer' | tail -20
```

Attendu : `New decisions: ...`, `streaming routine ticked`, pas d'erreur `401` ou `connection refused`.

### 3.5. Profiles chargés

```bash
docker exec crowdsec cscli profiles list -o human
```

Attendu : `ban_critical`, `ban_high`, `ban_medium`, `default_ban` — dans cet ordre.

### 3.6. Surface réseau inchangée

Depuis le laptop :

```bash
nmap -p 1-1024 <ip-vps>
```

Attendu : exactement `80/tcp open`, `443/tcp open`, `2203/tcp open|filtered`. **Aucun port nouveau** — CrowdSec ne publie rien sur l'host (ADR-002 respectée).

---

## 4. Test d'attaque (déclenche un ban réel)

À faire depuis un IP **autre que le laptop d'admin** (4G ou un VPS de test) — sinon on se ban soi-même. Confirmer son IP source avant : `curl -s https://api.ipify.org`.

```bash
# 60 requêtes pour `/.env?<random>` — déclenche http-sensitive-files / http-probing.
for i in $(seq 1 60); do
  curl -s -o /dev/null -w "%{http_code} " "https://portfolio.ldesfontaine.com/.env?$RANDOM"
done
echo
```

Attendu : un mix de `404` au début, puis bascule en `403` (le plugin Traefik bloque avec le code de remediation par défaut — réponse vide ou page d'erreur Traefik).

Côté VPS, vérifier la décision posée :

```bash
docker exec crowdsec cscli decisions list
```

Doit afficher une ligne avec l'IP source du laptop de test, `scenario: crowdsecurity/http-sensitive-files` (ou similaire), `type: ban`, `duration: 4h` (cf. `ban_high`).

Vérifier aussi l'alerte :

```bash
docker exec crowdsec cscli alerts list
```

### 4.1. Test d'unban manuel

```bash
docker exec crowdsec cscli decisions delete --ip <ton.ip.publique>
```

Re-curl la même requête → repasse en `404` (le portfolio ne sert pas `/.env` mais le bouncer ne bloque plus).

---

## 5. Idempotence

```bash
cd ansible
ansible-playbook -i inventory/00-static.yml playbooks/deploy-vps-services.yml \
  --tags pangolin,crowdsec --diff
```

Doit afficher `changed=0` sur **les deux** rôles. Si `changed > 0` sans modification :

- Côté pangolin → souvent un re-render YAML qui décale les sauts de ligne. Diff le `.backup` généré pour identifier.
- Côté crowdsec → s'assurer que `_crowdsec_lapi_status` (cscli lapi status) est bien noté `changed_when: false`, et que le bouncer existait déjà au listing.

---

## 6. Activation CrowdSec Console (procédure ultérieure)

L'enrôlement permet de centraliser les décisions sur le dashboard `app.crowdsec.net` et d'activer les blocklists CTI communautaires (CrowdSec en mode "Smoke Test" gratuit fournit déjà la liste des IPs malveillantes corrélées sur 100k+ déploiements).

1. Créer un compte sur https://app.crowdsec.net si pas déjà fait.
2. Dashboard → **Security Engines** → **Add a Security Engine** → copier la commande générée. La clé est de la forme `cscli console enroll <ENROLL_KEY>` — on ne récupère que `<ENROLL_KEY>`.
3. `ansible-vault edit ansible/inventory/group_vars/vps/vault.yml`. Remplacer la valeur de `vault_crowdsec_enroll_key` par la clé copiée.
4. Rejouer le rôle crowdsec :

   ```bash
   cd ansible
   ansible-playbook -i inventory/00-static.yml playbooks/deploy-vps-services.yml \
     --tags crowdsec --diff
   ```

   La task `Enroll agent in CrowdSec Console` exécute `cscli console enroll`. Si déjà enrôlé (re-run), le `failed_when` filtre le message "already enrolled" → idempotent.

5. Dashboard CrowdSec → l'agent apparaît en pending, cliquer **Accept**.
6. Dashboard → **Blocklists** → activer "CrowdSec Community Blocklist" (et toute autre liste souhaitée).
7. Sur l'agent, vérifier que les blocklists sont pullées :

   ```bash
   docker exec crowdsec cscli decisions list --origin lists | head -5
   ```

À chaque run du playbook, `DISABLE_ONLINE_API` est recalculé : si la clé est posée, l'env passe à `false` et le compose recrée le container (changement de variable d'environnement). C'est attendu une fois (au moment du toggle), puis idempotent.

---

## 7. Troubleshooting

### 7.1. Le plugin Traefik échoue au boot

Symptôme : `docker logs traefik` montre `failed to load plugin crowdsec-bouncer: ...` ou `error compiling plugin`.

Diagnostic :
- Vérifier que `pangolin_traefik_plugin_crowdsec_version` pointe une release existante côté GitHub et compatible Traefik v3.
- Cache plugin Traefik corrompu :
  ```bash
  docker exec traefik ls /plugins-storage
  sudo docker compose -f /opt/pangolin/docker-compose.yml restart traefik
  ```
- En dernier recours, supprimer le cache plugin et laisser Traefik le re-télécharger :
  ```bash
  sudo docker compose -f /opt/pangolin/docker-compose.yml down traefik
  sudo rm -rf /opt/pangolin/config/traefik/plugins-storage   # si présent
  sudo docker compose -f /opt/pangolin/docker-compose.yml up -d traefik
  ```

### 7.2. Bouncer en `401 Unauthorized`

Symptôme : `docker logs traefik` montre `401 calling crowdsec LAPI`.

Cause : la valeur de `vault_crowdsec_bouncer_key` côté Ansible diffère de celle enregistrée dans la base CrowdSec (probable si on a régénéré la clé sans rejouer le rôle crowdsec).

Fix :

```bash
# 1. Côté CrowdSec, supprimer le bouncer pour qu'Ansible le recrée :
docker exec crowdsec cscli bouncers delete traefik-bouncer

# 2. Rejouer le rôle crowdsec :
cd ansible
ansible-playbook -i inventory/00-static.yml playbooks/deploy-vps-services.yml \
  --tags crowdsec --diff

# 3. Traefik recharge le middleware via file watch — sinon redémarrer :
ssh -p 2203 deploy@<ip-vps> 'sudo docker compose -f /opt/pangolin/docker-compose.yml restart traefik'
```

### 7.3. Zéro ligne parsée par l'agent

Symptôme : `cscli metrics` affiche `lines parsed = 0` sur `/var/log/traefik/access.log`.

Causes possibles :

- Le format n'est pas JSON → le parser `crowdsecurity/traefik` accepte JSON, alors qu'on était en `common`/CLF avant.
  ```bash
  sudo head -1 /opt/pangolin/config/traefik/logs/access.log
  ```
  Doit commencer par `{"...":` (JSON). Si ce n'est pas le cas, le rôle pangolin n'a pas relancé Traefik (handler manqué) — re-run avec `--tags pangolin`, ou redémarrer Traefik manuellement.
- Le bind-mount n'est pas effectif :
  ```bash
  docker exec crowdsec ls -l /var/log/traefik/access.log
  ```
  Si `No such file` → le path `crowdsec_traefik_logs_host_path` côté défaults ne correspond pas au chemin réel des logs Traefik. Vérifier `_pangolin_traefik_logs_dir` dans `roles/pangolin/vars/main.yml`.

### 7.4. Container CrowdSec en restart loop

Diagnostic :

```bash
docker logs crowdsec --tail 100
```

Cas typiques :

- `permission denied` sur `/var/log/auth.log` → le cap `DAC_READ_SEARCH` n'a pas été pris en compte. Vérifier `cap_add: [DAC_READ_SEARCH]` dans le compose, recreate le container.
- `unable to parse acquis.yaml` → erreur de syntaxe dans le template. Re-render et restart :
  ```bash
  sudo cat /opt/crowdsec/config/acquis.yaml | docker run --rm -i mikefarah/yq:4 .
  ```
  Doit ne retourner aucune erreur.
- `database is locked` → conflit sur la base SQLite locale. Stopper le container, vérifier qu'aucun autre process ne tient `/opt/crowdsec/data/crowdsec.db`, restart.

### 7.5. Le bouncer banit nos propres requêtes

Symptôme : depuis l'IP admin on est `403` alors qu'on n'a rien fait de suspect.

Cause : le bouncer a banni l'IP du reverse hop (Docker bridge IP) parce que `forwardedHeadersTrustedIPs` ne le couvre pas → tous les clients sont vus comme cette IP. Décision globale qui banit tout le trafic.

Fix : vérifier dans `roles/pangolin/templates/dynamic_config.yml.j2` que les blocs `forwardedHeadersTrustedIPs` et `clientTrustedIPs` listent au minimum `127.0.0.1/32` et `172.16.0.0/12` (couvre `pangolin-net` 172.19.0.0/16). Si l'IP du bridge interne diffère, l'élargir.

Unban d'urgence :

```bash
docker exec crowdsec cscli decisions delete --all
```

(supprime toutes les décisions actives — à utiliser uniquement en récupération).

---

## 8. Rollback

### 8.1. Désactiver le bouncer sans toucher à l'agent

Surcharger `pangolin_crowdsec_integration_enabled: false` (extra-vars CLI ou édition `roles/pangolin/defaults/main.yml`), rejouer `--tags pangolin --diff`. La conf statique Traefik perd la déclaration du plugin (handler `Restarting traefik` déclenché), la conf dynamique ne définit plus le middleware ni son attachement aux routers backend. CrowdSec continue de tourner et d'ingérer les logs — utile pour observer sans bloquer, ou pour debug Pangolin/Traefik isolément.

```bash
ansible-playbook -i inventory/00-static.yml playbooks/deploy-vps-services.yml \
  --tags pangolin -e pangolin_crowdsec_integration_enabled=false --diff
```

Pour réactiver : retirer l'extra-var (ou repasser à `true`) et rejouer.

### 8.2. Retirer complètement CrowdSec

Couper le rôle crowdsec dans le playbook (commenter l'entrée), puis nettoyer le VPS :

```bash
ssh -p 2203 deploy@<ip-vps>
sudo docker compose -f /opt/crowdsec/docker-compose.yml down -v
sudo rm -rf /opt/crowdsec
```

Côté Traefik, retirer aussi le plugin et le middleware (revert des deux templates pangolin). Sinon Traefik plante au boot (plugin présent dans static config sans agent joignable peut survivre, mais le middleware référencé dans dynamic_config provoquera des erreurs au routing).

### 8.3. Rollback complet vers session 4

```bash
git revert <sha-session-5-commits>   # ou git reset --hard <sha-session-4>
cd ansible
ansible-playbook -i inventory/00-static.yml playbooks/deploy-vps-services.yml \
  --tags pangolin --diff
ssh -p 2203 deploy@<ip-vps> 'sudo docker compose -f /opt/crowdsec/docker-compose.yml down -v && sudo rm -rf /opt/crowdsec'
```

Aucun impact DNS, le portfolio reste accessible.

---

## 9. Limites connues — reportées aux sessions suivantes

- **Pas d'AppSec** : la collection `crowdsec-appsec` n'est PAS installée. Le bouncer fonctionne en mode "decision streaming" classique, pas en mode WAF inline. Si on en a besoin (e.g. blocage XSS/SQLi en temps réel), prévoir une session dédiée.
- **Pas de captcha** : décision projet — on banit ou on laisse passer, jamais d'étape captcha. Si on change d'avis (UX vs sécurité), revoir `profiles.yaml.j2` et envisager un middleware captcha Traefik.
- **Pas de monitoring/alerting** : aucune notification sur ban (Slack, mail). À câbler sur Grafana/Loki ou via la Console CrowdSec (session 7+).
- **Pas de backup spécifique** : la base SQLite locale (`/opt/crowdsec/data/crowdsec.db`) contient l'historique des décisions. Pas critique tant qu'on tourne en isolation — à intégrer à la stratégie PBS plus tard.
- **Renouvellement clé bouncer** : aucune procédure automatisée. À documenter quand on aura un process de rotation des secrets vault (session backup/PBS).

---

## 10. Journal d'exécution

| Date | Opérateur | `changed=` (pangolin) | `changed=` (crowdsec) | Test attaque OK ? | Notes |
|---|---|---|---|---|---|
|  |  |  |  |  |  |
