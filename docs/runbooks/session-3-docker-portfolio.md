# Runbook — Session 3 : Docker + ufw-docker + portfolio

> **Statut** : actif — v1.0 — auteur `ldesfontaine`
> **Référence** : `docs/adr/ADR-000-fondations-ansible.md` (Décision 6), `docs/adr/ADR-002-firewall-strategy.md`
> **Playbook** : `ansible/playbooks/deploy-vps-services.yml`

Objectif de la session : installer Docker CE depuis le repo officiel, intégrer `chaifeng/ufw-docker` dans la chaîne `DOCKER-USER` (couche 2 de l'ADR-002), et déployer le container portfolio en pull depuis GHCR avec un binding `127.0.0.1` (testable via SSH tunnel). Aucune exposition publique du portfolio à ce stade — Pangolin viendra le router en session 4.

---

## 1. Prérequis

- Sessions 1 (bootstrap) et 2 (hardening) jouées avec succès, idempotence prouvée — `ssh -p 2203 deploy@<ip>` fonctionne, sudo NOPASSWD, fail2ban actif.
- Image `ghcr.io/ldesfontaine/portfolio:0.0.4` (ou tag plus récent) publiée et **publique** sur GHCR. Si l'image est privée, il faudra ajouter une étape `community.docker.docker_login` avec un PAT GHCR vaultisé — pas couvert par cette session.
- Vault contient `vault_portfolio_payload_secret` avec une valeur réelle (pas placeholder). Si absent, voir §2.
- `ssh-agent` actif sur le poste de pilotage, clé `~/.ssh/id_ed25519_homelab` chargée.
- Mot de passe vault en place : `~/.ansible/vault-pass-homelab.txt` lisible.
- Console KVM Hetzner accessible (voie de récupération si UFW casse).
- Collections installées :

  ```bash
  cd ansible
  ansible-galaxy collection install -r requirements.yml
  ```

  En particulier `community.docker` ≥ 3.10.0 pour `docker_compose_v2` :

  ```bash
  ansible-galaxy collection list community.docker
  ```

## 2. Validation pré-vol

### 2.1. Générer / mettre à jour le secret Payload (si pas encore fait)

```bash
openssl rand -base64 48
ansible-vault edit ansible/inventory/group_vars/vps/vault.yml
# Ajouter / mettre à jour :
#   vault_portfolio_payload_secret: "<valeur openssl>"
```

Vérifier que la variable applicative résout :

```bash
cd ansible
ansible -m debug -a 'var=portfolio_payload_secret' vps-pangolin
```

La sortie doit être la valeur du secret (et **pas** la chaîne `{{ vault_portfolio_payload_secret }}` ni `VARIABLE IS NOT DEFINED`). Cette commande affiche le secret en clair dans le terminal — fermer l'historique shell après usage.

### 2.2. Syntaxe + lint

```bash
cd ansible
ansible-playbook playbooks/deploy-vps-services.yml --syntax-check
ansible-lint
yamllint -c ../.yamllint .
```

### 2.3. Ping

```bash
ansible -i inventory vps-pangolin -m ping
```

Doit retourner `pong` via `deploy@2203` (détection auto via `_detect-ssh.yml`).

## 3. Procédure d'exécution

### 3.1. Dry-run

```bash
cd ansible
ansible-playbook playbooks/deploy-vps-services.yml --check --diff
```

⚠️ **Limite connue** (cohérente avec ADR-000 Décision 4) : le rôle `docker` peut échouer en check mode sur les tasks dépendantes d'un état créé en runtime (ex : `apt install docker-ce` puis `service docker started`). C'est attendu — la validation de cette session se fait par l'idempotence post-run. Lire le diff sur ce qui passe (template `daemon.json`, blockinfile UFW, templates compose / env / cron).

### 3.2. Run réel

```bash
cd ansible
ansible-playbook playbooks/deploy-vps-services.yml
```

Moments critiques :
1. `Insert ufw-docker integration block into after.rules` puis handler `Reloading ufw` — si le fragment iptables est cassé, `ufw reload` échouera et UFW restera dans son état précédent (rollback automatique).
2. `Pull portfolio image` — peut prendre une minute selon la bande passante.
3. `Wait for portfolio HTTP availability` — boucle de 12 retries × 5s sur `http://127.0.0.1:3000/`. Échoue si Payload ne boote pas (cause habituelle : `PAYLOAD_SECRET` vide ou placeholder).

### 3.3. Runs ciblés (debug)

```bash
ansible-playbook playbooks/deploy-vps-services.yml --tags docker
ansible-playbook playbooks/deploy-vps-services.yml --tags ufw-docker
ansible-playbook playbooks/deploy-vps-services.yml --tags portfolio
ansible-playbook playbooks/deploy-vps-services.yml --tags portfolio-deploy
```

## 4. Post-run validation

### 4.1. Docker installé et actif

```bash
ssh -p 2203 deploy@<ip> 'docker --version && docker compose version'
```

Versions affichées (CE + plugin compose). Le user `deploy` peut lancer `docker ps` sans sudo après un re-login.

### 4.2. Daemon.json appliqué

```bash
ssh -p 2203 deploy@<ip> 'sudo cat /etc/docker/daemon.json'
```

Doit contenir `live-restore: true`, `userland-proxy: false`, `log-driver: json-file` avec rotation.

### 4.3. Portfolio container up

```bash
ssh -p 2203 deploy@<ip> 'docker ps --filter name=portfolio --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
```

Attendu : `Up X minutes (healthy)`, ports `127.0.0.1:3000->3000/tcp`.

### 4.4. Chaîne DOCKER-USER active

```bash
ssh -p 2203 deploy@<ip> 'sudo iptables -L DOCKER-USER -v --line-numbers'
```

Doit montrer la séquence ADR-002 : `RELATED,ESTABLISHED` → `RETURN` pour RFC1918 → `NEW` → `ufw-docker-logging-deny` → `LOG` + `DROP`.

### 4.5. UFW status

```bash
ssh -p 2203 deploy@<ip> 'sudo ufw status verbose'
```

Attendu :
- `Status: active`, `Logging: on`
- `2203/tcp ALLOW` (SSH)
- **Pas de `3000/tcp ALLOW`** — le binding 127.0.0.1 ne se traduit jamais en règle UFW publique.
- Pas d'autre port public.

### 4.6. Test via SSH tunnel (depuis le laptop)

```bash
# Ouvre le tunnel en background
ssh -L 3000:127.0.0.1:3000 -N -p 2203 deploy@<ip> &
TUNNEL_PID=$!

# Test
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
# Attendu : 200 (ou 301/302 selon le routing initial Payload)

# Refermer
kill "${TUNNEL_PID}"
```

### 4.7. Confirmation que le port 3000 N'EST PAS exposé publiquement

Depuis un autre réseau (smartphone 4G, autre VPS, n'importe où sauf le laptop déjà connecté) :

```bash
curl --max-time 5 http://<ip-vps>:3000
# Attendu : timeout ou "connection refused"
```

C'est **le** test qui valide la couche 1 (architecture) de l'ADR-002. S'il répond, **stop** et reconfigurer.

Compléter avec un scan :

```bash
nmap -p 22,2203,80,443,3000 <ip-vps>
# Attendu : 2203 open, le reste closed/filtered
```

### 4.8. Idempotence (le test qui valide vraiment la session)

```bash
cd ansible
ansible-playbook playbooks/deploy-vps-services.yml
```

Récap attendu : `changed=0` sur l'host VPS. Le `docker_compose_v2` peut occasionnellement reporter un `changed=1` cosmétique au tout premier re-run après création — si ça se reproduit aux runs suivants, identifier le module non idempotent.

### 4.9. Backups Payload

**Pas de cron host-side**. Les snapshots sont déclenchés manuellement depuis l'UI Payload sur `/admin` (section « Sauvegarde & restauration », endpoints `/api/snapshot` et `/api/snapshot/restore` — cf. repo `termfolio`). Le script `/app/scripts/backup.sh` mentionné dans le README portfolio n'existe pas dans l'image et ne doit pas être réintroduit en cron Ansible.

## 5. Rollback manuel

### 5.1. Container portfolio KO (Payload refuse de booter, healthcheck échoue)

```bash
ssh -p 2203 deploy@<ip>
cd /opt/portfolio
sudo docker compose logs portfolio --tail=200
# Cause habituelle :
#   - PAYLOAD_SECRET vide → ré-éditer le vault, rejouer --tags portfolio-deploy
#   - DATABASE_URI inaccessible → vérifier le volume `portfolio-data`
sudo docker compose down
sudo docker compose up -d
```

### 5.2. Image cassée (Payload qui ne boote pas avec le nouveau tag)

Rollback au tag précédent :

```bash
# Éditer ansible/inventory/group_vars/vps/vars.yml (ou roles/portfolio/defaults/main.yml)
portfolio_image_tag: "<version précédente>"
# Rejouer
cd ansible
ansible-playbook playbooks/deploy-vps-services.yml --tags portfolio-deploy
```

### 5.3. ufw-docker cassé (UFW reload échoue, ou trafic légitime bloqué)

Le block est délimité par les markers Ansible `# BEGIN ANSIBLE MANAGED BLOCK ufw-docker integration (ADR-002)` et `# END ...`.

```bash
# Via console Hetzner ou SSH si encore possible
sudo cp /etc/ufw/after.rules /etc/ufw/after.rules.broken
sudo sed -i '/BEGIN ANSIBLE MANAGED BLOCK ufw-docker/,/END ANSIBLE MANAGED BLOCK ufw-docker/d' /etc/ufw/after.rules
sudo ufw reload
```

Le `backup: true` du blockinfile a déjà créé un `/etc/ufw/after.rules.XXX.bak` — possible aussi de restaurer celui-là.

### 5.4. Docker daemon cassé (n'arrive pas à démarrer)

```bash
ssh -p 2203 deploy@<ip>
sudo journalctl -u docker -n 100 --no-pager
# Cause habituelle : JSON invalide dans /etc/docker/daemon.json
sudo mv /etc/docker/daemon.json{,.broken}
# Restaurer le backup posé par Ansible
sudo cp /etc/docker/daemon.json.XXXX.bak /etc/docker/daemon.json
sudo systemctl restart docker
```

### 5.5. Re-login `deploy` pour bénéficier du groupe `docker`

Si `docker ps` sans sudo retourne `permission denied`, c'est juste un re-login à faire :

```bash
exit
ssh -p 2203 deploy@<ip>
id deploy   # docker doit apparaître dans les groupes
```

## 6. Limites connues — explicitement reportées aux sessions suivantes

- **Portfolio binding `127.0.0.1:3000` uniquement** : pas accessible publiquement (voulu). La session 4 (Pangolin) basculera `portfolio_bind_localhost: false`, retirera le bloc `ports:`, et joindra le container au réseau partagé `pangolin-net`.
- **Pas de TLS, pas de domaine routé** : session 4.
- **Pas de CrowdSec / bouncer Traefik** : session 5. La couche 2 ufw-docker fait office de filet en attendant.
- **Pas de WireGuard hub** : session 6.
- **Image GHCR supposée publique** : si on bascule en privé, ajouter `community.docker.docker_login` + PAT GHCR vaultisé.
- **`vault_portfolio_payload_secret` doit être une valeur réelle** : tout placeholder fera échouer le boot Payload et le healthcheck `uri:`.
- **`validate:` sur le blockinfile ufw-docker non posé** : `iptables-restore --test` est fragile sous nftables-backend (Debian Trixie via `iptables-nft`). On compte sur `backup: true` et l'échec bruyant du handler `Reloading ufw` pour détecter une régression — l'ancienne config reste en place dans ce cas.
- **Backups Payload gérés manuellement** : pas de cron host-side dans le rôle. Snapshots déclenchés via l'UI `/admin` du portfolio (cf. §4.9). À reconsidérer le jour où le repo `termfolio` embarque un vrai script `backup.sh` dans l'image.

## 7. Journal d'exécution

| Date | Opérateur | Host | Résultat | Notes |
|---|---|---|---|---|
| | `ldesfontaine` | `vps-pangolin` | | |
