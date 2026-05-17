# Runbook — Session 6 : hub WireGuard admin natif sur le VPS

> **Statut** : actif — v1.0 — auteur `ldesfontaine`
> **Référence** : `docs/adr/ADR-002-firewall-strategy.md` (51821/udp ouvert en UFW INPUT classique — natif host, hors DOCKER-USER), `docs/adr/ADR-000-fondations-ansible.md` (idempotence, no_log secrets, perms explicites)
> **Playbook** : `ansible/playbooks/deploy-vps-services.yml`
> **Rôles touchés** : `wg_admin_hub` (nouveau)

Objectif de la session : monter un **hub WireGuard natif sur le VPS** (systemd `wg-quick@wg-admin`, hors Docker) pour pré-câbler l'accès admin distant aux futurs services internes (monitoring, IDP, coffre, etc.). Subnet `10.99.10.0/24`, hub à `10.99.10.1`, écoute UDP `51821`, deux peers admin déclarés (laptop + phone). Le futur peer OPNsense maison est conservé en placeholder commenté pour la phase Proxmox. **Note** : le dashboard Pangolin n'est PAS joignable via ce tunnel (architecture reverse-proxy Host-aware — cf. §7.2), il continue de passer par SSH tunnel jusqu'à Phase 11 (Authentik + exposition publique).

À la fin de la session : `wg show wg-admin` côté VPS liste les deux peers, le laptop monte le tunnel avec `wg-quick up homelab` et pingue `10.99.10.1`, le phone fait pareil via QR code, `nmap` depuis l'extérieur n'expose **aucun port nouveau hors `51821/udp`** (et toujours `80/tcp`, `443/tcp`, `2203/tcp`).

---

## 1. Prérequis

- Sessions 1 → 5 jouées avec succès. Idempotence prouvée sur `deploy-vps-services.yml` (`changed=0` au 2ème run).
- `ssh -p 2203 deploy@<ip-vps>` fonctionne, `sudo` NOPASSWD configuré.
- `ssh-agent` chargé avec `~/.ssh/id_ed25519_homelab`, mot de passe vault dispo (`~/.ansible/vault-pass-homelab.txt`).
- Collections Ansible à jour (`community.general` ≥ 10 pour le module `ufw`) :

  ```bash
  cd ansible
  ansible-galaxy collection install -r requirements.yml
  ```

### 1.1. Génération des paires de clés client (en local, chez Lucas)

Les privkeys client ne quittent **jamais** la machine cliente. Sur le laptop, créer un dossier de travail dédié :

```bash
mkdir -p ~/.config/wireguard/homelab
cd ~/.config/wireguard/homelab
umask 077

# Paire pour le laptop
wg genkey | tee laptop-priv.key | wg pubkey > laptop-pub.key

# Paire pour le phone
wg genkey | tee phone-priv.key  | wg pubkey > phone-pub.key

ls -la
# laptop-priv.key et phone-priv.key DOIVENT être en 0600.
```

Conserver les `*-priv.key` localement (les fichiers `.conf` clients les référenceront), copier les **pubkeys** pour les déposer au vault à l'étape suivante.

### 1.2. Édition du vault VPS

```bash
ansible-vault edit ansible/inventory/group_vars/vps/vault.yml
```

Vérifier (ou ajouter) les entrées :

```yaml
# Pubkeys WireGuard des peers admin — déposées par Lucas après
# `wg genkey | wg pubkey` en local. Les privkeys correspondantes restent
# uniquement sur la machine cliente (laptop, phone).
vault_wg_peer_laptop_pubkey: "<contenu de laptop-pub.key>"
vault_wg_peer_phone_pubkey:  "<contenu de phone-pub.key>"
```

> **Note** : si `vault_wg_peer_laptop_pubkey` ou `vault_wg_peer_phone_pubkey` est absent du vault, le rôle `wg_admin_hub` **plante tôt** au render du template (`'vault_wg_peer_...' is undefined`) — fail-fast volontaire, on ne déploie pas un hub avec un peer vide.

### 1.3. Record DNS

Côté Cloudflare → zone `ldesfontaine.com` → ajouter `wg-hub` `A` → `62.72.36.161`, proxy **DNS only** (orange désactivé). Cloudflare ne sait pas proxyfier l'UDP, le tunnel doit taper directement le VPS.

Vérifier la résolution depuis le laptop :

```bash
dig +short wg-hub.ldesfontaine.com
# Doit retourner 62.72.36.161
```

### 1.4. Outillage local

```bash
# Linux laptop
sudo apt install wireguard-tools qrencode
```

`wireguard-tools` fournit `wg`, `wg-quick` (côté client). `qrencode` sert à générer le QR pour le phone à l'étape 6.

### 1.5. Validation pré-vol

```bash
cd ansible

# Syntaxe
ansible-playbook playbooks/deploy-vps-services.yml --syntax-check

# Lint
ansible-lint roles/wg_admin_hub
yamllint -c ../.yamllint roles/wg_admin_hub playbooks/deploy-vps-services.yml

# Dry-run — UNIQUEMENT après le premier run réel (voir note ci-dessous)
ansible-playbook -i inventory/00-static.yml playbooks/deploy-vps-services.yml \
  --check --diff --tags wg_admin_hub
```

> **Limitation `--check` au premier déploiement** : la chaîne `generate
> privkey → enforce perms → slurp → derive pubkey → render conf` du rôle
> dépend de la présence réelle de `/etc/wireguard/wg-admin.key` sur disque.
> En check mode, la task `Generate the WireGuard private key (only if
> absent)` simule sans écrire, donc la task suivante `Enforce 0600 perms on
> the WireGuard private key` plante avec `file (/etc/wireguard/wg-admin.key)
> is absent, cannot continue`. C'est la même limitation Ansible que pour
> le rôle `bootstrap` (cf. ADR-000, section "Limite acceptée — check mode
> partiel").
>
> **Au premier déploiement** : skip la commande `--check` ci-dessus et
> lance directement le run effectif (section 2). Une fois la privkey
> créée sur disque, `--check` passe proprement à tous les runs suivants
> et reste utile pour valider l'idempotence avant un run réel.

---

## 2. Exécution

```bash
cd ansible
ansible-playbook -i inventory/00-static.yml playbooks/deploy-vps-services.yml \
  --tags wg_admin_hub --diff
```

Effets attendus au premier run :

- Paquet `wireguard` installé (sur Trixie il pulle `wireguard-tools` en dépendance).
- `/etc/wireguard/` créé en `0700 root:root`.
- `/etc/wireguard/wg-admin.key` généré via `wg genkey` (uniquement si absent — `creates:`), perms forcées `0600 root:root`.
- `/etc/wireguard/wg-admin.pub` posé en `0644 root:root` (clé publique, distributable).
- `/etc/wireguard/wg-admin.conf` rendu en `0600 root:root` (handler `Restarting wireguard hub` déclenché).
- `/etc/sysctl.d/99-wireguard-forward.conf` posé en `0644 root:root` (handler `Reloading sysctl` déclenché).
- Règle UFW `ALLOW IN  51821/udp` ajoutée (commentée `WireGuard admin hub (wg-admin)`).
- Unit `wg-quick@wg-admin.service` enabled + started.
- Handlers flushés avant le health check pour appliquer le restart pending.
- `wg show wg-admin` retourne `rc=0` (au plus quelques retries le temps que l'unit converge).
- Affichage debug final : pubkey VPS, endpoint, IP hub, liste des peers. **Copier la pubkey** — elle sert aux fichiers `.conf` clients.

Premier run : `changed > 0`. Deuxième run consécutif : `changed=0` (cf. section 8).

> **Attention** : si Lucas est connecté au hub WG au moment du run (sessions ultérieures), le handler `Restarting wireguard hub` **coupe le tunnel ~2-3 secondes**. Pour la session 6 initiale, personne n'est encore connecté → non-événement. Pour les runs futurs : se déconnecter du tunnel avant le run, ou rejouer depuis une connexion non-WG.

---

## 3. Vérifications côté VPS

Depuis `ssh -p 2203 deploy@<ip-vps>` :

### 3.1. Service systemd

```bash
sudo systemctl status wg-quick@wg-admin
```

Attendu : `Active: active (exited)` (les unit `wg-quick@*` sont oneshot — l'interface est montée par `wg-quick up`, le process exit, c'est normal).

### 3.2. Interface WireGuard

```bash
sudo wg show wg-admin
```

Attendu :
```
interface: wg-admin
  public key: <pubkey du hub>
  private key: (hidden)
  listening port: 51821

peer: <pubkey laptop>
  allowed ips: 10.99.10.10/32

peer: <pubkey phone>
  allowed ips: 10.99.10.11/32
```

Pas de `latest handshake` encore — aucun client n'a tenté de se connecter à ce stade. C'est attendu.

### 3.3. UFW

```bash
sudo ufw status verbose | grep -E '51821|WireGuard'
```

Attendu : `51821/udp  ALLOW IN  Anywhere  # WireGuard admin hub (wg-admin)`.

### 3.4. Socket réellement en écoute

```bash
sudo ss -ulnp | grep 51821
```

Attendu : une ligne `UNCONN  ... 0.0.0.0:51821 ... users:(("wg",...))` ou équivalent (le module kernel WireGuard tient le socket — le nom de processus peut varier).

### 3.5. IP forwarding persisté

```bash
sysctl net.ipv4.ip_forward
sudo cat /etc/sysctl.d/99-wireguard-forward.conf
```

Attendu : `net.ipv4.ip_forward = 1` côté runtime ET dans le fichier.

### 3.6. Perms fichier critique

```bash
sudo ls -la /etc/wireguard/
```

Attendu :
- `wg-admin.key` → `-rw------- 1 root root`
- `wg-admin.pub` → `-rw-r--r-- 1 root root`
- `wg-admin.conf` → `-rw------- 1 root root`

### 3.7. Surface réseau publique inchangée (hors 51821/udp)

Depuis le laptop, pas depuis le VPS :

```bash
nmap -sU -p 51821 <ip-vps>          # UDP — doit montrer 51821 open|filtered
nmap -p 1-1024 <ip-vps>             # TCP — doit montrer 80, 443, 2203 et c'est tout
```

Aucun autre port nouveau. ADR-002 respectée — le seul ajout par rapport à la session 5 est `51821/udp`.

---

## 4. Construction des fichiers `.conf` client (en local, chez Lucas)

### 4.1. Récupérer la pubkey VPS

Trois moyens équivalents :

```bash
# (a) Depuis la sortie debug du dernier run Ansible — scroller la sortie de la task
#     "Show client-side connection info".

# (b) Depuis le VPS directement
ssh -p 2203 deploy@<ip-vps> 'sudo cat /etc/wireguard/wg-admin.pub'

# (c) Via Ansible
cd ansible
ansible vps -i inventory/00-static.yml -b -m ansible.builtin.slurp \
  -a 'src=/etc/wireguard/wg-admin.pub' | grep content | awk '{print $2}' | base64 -d
```

### 4.2. Template `laptop.conf`

```bash
cat > ~/.config/wireguard/homelab/laptop.conf <<EOF
[Interface]
PrivateKey = $(cat ~/.config/wireguard/homelab/laptop-priv.key)
Address    = 10.99.10.10/32
DNS        = 1.1.1.1

[Peer]
PublicKey           = <pubkey VPS (étape 4.1)>
Endpoint            = wg-hub.ldesfontaine.com:51821
AllowedIPs          = 10.99.10.0/24
PersistentKeepalive = 25
EOF
chmod 0600 ~/.config/wireguard/homelab/laptop.conf
```

`AllowedIPs = 10.99.10.0/24` route **uniquement le trafic vers le subnet admin** à travers le tunnel (split-tunnel). Le reste de la navigation laptop passe normalement par la connexion locale. Si à terme on veut full-tunnel via le hub, remplacer par `0.0.0.0/0` (et adapter la conf du hub pour autoriser le NAT sortant — hors scope session 6).

### 4.3. Template `phone.conf`

Même template, en remplaçant :
- `PrivateKey` → contenu de `phone-priv.key`
- `Address` → `10.99.10.11/32`

```bash
cat > ~/.config/wireguard/homelab/phone.conf <<EOF
[Interface]
PrivateKey = $(cat ~/.config/wireguard/homelab/phone-priv.key)
Address    = 10.99.10.11/32
DNS        = 1.1.1.1

[Peer]
PublicKey           = <pubkey VPS (étape 4.1)>
Endpoint            = wg-hub.ldesfontaine.com:51821
AllowedIPs          = 10.99.10.0/24
PersistentKeepalive = 25
EOF
chmod 0600 ~/.config/wireguard/homelab/phone.conf
```

---

## 5. Activation côté laptop Linux

```bash
# Installer la conf à l'emplacement standard wg-quick
sudo install -m 0600 -o root -g root \
  ~/.config/wireguard/homelab/laptop.conf /etc/wireguard/homelab.conf

# Monter le tunnel
sudo wg-quick up homelab

# Vérifier l'état
sudo wg show
# Attendu : interface "homelab" avec un peer (VPS), latest handshake récent (qq s).

# Ping du hub à travers le tunnel
ping -c 3 10.99.10.1
# Attendu : 3 réponses, ~latence Hetzner (10-30 ms).

# Test fonctionnel — le hub répond bien à l'IP côté tunnel
ping -c 1 10.99.10.1 >/dev/null && echo "tunnel up"
# Pas de dashboard à tester ici : aucun service interne ne binde sur
# 10.99.10.1 pour l'instant (cf. §7.2 — Pangolin nécessite une approche
# Host-aware, pas un binding direct).
```

Pour activer le tunnel automatiquement au boot du laptop : `sudo systemctl enable wg-quick@homelab`. **Optionnel** — préférable de l'activer manuellement quand on en a besoin.

### 5.1. Démontage propre

```bash
sudo wg-quick down homelab
```

---

## 6. Activation côté phone iOS (méthode QR code)

L'app WireGuard iOS sait importer une conf via QR code. La conf est petite (~300 octets), un QR ANSI dans le terminal suffit.

```bash
# Sur le laptop, dans le terminal — le QR s'affiche en blocs unicode
qrencode -t ANSIUTF8 < ~/.config/wireguard/homelab/phone.conf
```

Sur le phone :
1. Installer l'app **WireGuard** (App Store, par WireGuard Development Team).
2. Ouvrir → `+` (en haut à droite) → **Create from QR code**.
3. Scanner le QR affiché dans le terminal du laptop.
4. Nom du tunnel proposé : `homelab` (ou ce que tu veux).
5. Activer le toggle du tunnel.
6. Test : app gratuite type **Network Ping Lite** → ping `10.99.10.1`. (Pas de dashboard Pangolin atteignable par binding direct sur l'IP du tunnel — cf. §7.2.)

> **Sécurité** : effacer le QR de l'historique du terminal après import (`clear; history -c` si shell partagé). Le QR contient la **privkey** du phone.

---

## 7. Tests bout-en-bout

### 7.1. Côté VPS — handshake confirmé

```bash
ssh -p 2203 deploy@<ip-vps>
sudo wg show wg-admin
```

Une fois le laptop connecté, la section `peer: <pubkey laptop>` doit afficher :
- `latest handshake: <quelques secondes ago>`
- `transfer: ... received, ... sent`

Idem pour le phone après activation.

### 7.2. Accès dashboard Pangolin — limitation acceptée, reportée phase 11

**Le dashboard Pangolin n'est pas atteignable via le tunnel admin de cette session — ni par binding IP:port direct, ni par SSH tunnel.** Pangolin est une application **Host-aware** : son middleware Next.js compare le `Host` header reçu à la `dashboard_url` configurée (`pangolin.ldesfontaine.com`), et empile des vérifications additionnelles (origin CSRF, cookies de session liés au domaine). Conséquence : toute tentative de joindre le dashboard via une URL ne correspondant pas au FQDN configuré — qu'on tape directement `http://10.99.10.1:3000`, qu'on monte un SSH tunnel `localhost:3000 → container:3000`, ou qu'on bricole un `--header "Host: pangolin.ldesfontaine.com"` — renvoie `404` ou `403` même quand le serveur est joint correctement au niveau TCP. Une tentative initiale d'exposer `10.99.10.1:3000:3000` côté compose pangolin a été retirée pour cette raison (cf. commit `revert(pangolin): drop wg-admin port binding`), et l'option SSH tunnel a été testée puis abandonnée pour les mêmes raisons.

**Décision session 6 — limitation acceptée.** Le tunnel admin reste utile et nécessaire pour la catégorie des services **IP-friendly** (OPNsense, monitoring, coffres, tout service qui répond à une IP nue). Pour Pangolin, qui est **Host-aware**, on accepte de ne pas avoir d'accès admin pendant la phase actuelle. La classification "IP-friendly vs Host-aware" est formalisée dans [ADR-003](../adr/ADR-003-services-host-aware-vs-ip-friendly.md).

**Résolution — Phase 11.** Exposition publique de `pangolin.ldesfontaine.com` derrière Authentik (OIDC) + reverse proxy interne. Le dashboard sera alors atteignable par son FQDN, en passant par la chaîne d'auth Authentik, sans tunnel ni binding direct. C'est la voie d'admin standard pour tous les services Host-aware du homelab à venir.

### 7.3. Bascule laptop ↔ phone

Une fois le laptop validé : `sudo wg-quick down homelab`. Activer le tunnel sur le phone. Re-vérifier `sudo wg show wg-admin` côté VPS : `latest handshake` change de peer.

---

## 8. Idempotence

```bash
cd ansible
ansible-playbook -i inventory/00-static.yml playbooks/deploy-vps-services.yml \
  --tags wg_admin_hub --diff
```

Doit afficher `changed=0`. Les tasks read-only (`Derive the WireGuard public key`, `Verify the WireGuard interface is up`) ont `changed_when: false` et n'apparaissent donc pas comme changements.

Si `changed > 0` sans modification réelle :
- Souvent un re-render qui décale les sauts de ligne dans `wg-admin.conf`. Diff le `.backup` généré pour identifier.
- Si la pubkey VPS est régénérée → c'est le bug. Vérifier que `/etc/wireguard/wg-admin.key` n'a pas été supprimé manuellement (la task `Generate ... (only if absent)` régénérerait, et le restart casserait les peers existants — il faudrait redistribuer la nouvelle pubkey).

---

## 9. Sessions futures

### 9.1. Ajout du peer OPNsense maison (phase Proxmox/OPNsense)

Quand la VM OPNsense sera up et que le tunnel maison ↔ VPS devra router le LAN domestique (10.10.x.x) vers les services internes du VPS, l'ajout se fait sans toucher au reste de la stack :

1. Générer la paire WG côté OPNsense (UI plugin WireGuard ou CLI).
2. `ansible-vault edit ansible/inventory/group_vars/vps/vault.yml` → ajouter `vault_wg_peer_opnsense_pubkey: "<pubkey>"`.
3. Dans `ansible/roles/wg_admin_hub/defaults/main.yml` → décommenter le bloc `opnsense-home` (commentaire en tête de `wg_admin_hub_peers`) et le repositionner dans la liste.
4. Rejouer le rôle : `ansible-playbook ... --tags wg_admin_hub --diff`. Le hub ajoute la `[Peer]` section, handler `Restarting wireguard hub` déclenché — coupure brève (cf. section 2 attention).
5. Côté OPNsense, configurer son peer client avec l'endpoint `wg-hub.ldesfontaine.com:51821` + pubkey VPS + AllowedIPs `10.99.10.0/24` (ou élargi selon besoin de routage retour).

Le forwarding IPv4 est déjà actif sur le hub (sysctl + PostUp iptables) — pas de modif côté VPS au-delà du décommentage.

### 9.2. Évolutions à anticiper

- **PreSharedKey par peer** : pour défense en profondeur (compromission d'une privkey client), ajouter `PresharedKey` dans la conf de chaque peer. Nécessite vault + extension du template — à faire si modèle de menace évolue.
- **Hardening sshd via WG only** : à terme, restreindre `sshd_config` à `ListenAddress 10.99.10.1` (et 51820 newt côté pangolin) pour fermer 2203/tcp sur l'IP publique. Décision projet — pas pour cette session.
- **MFA via Authentik devant les UI internes** : aujourd'hui le tunnel WG est le seul facteur. Quand Authentik sera up (futur), couche additionnelle.

---

## 10. Troubleshooting

### 10.1. `wg show` côté VPS ne montre aucun handshake après activation client

Symptôme : `latest handshake` reste absent sur le peer, le ping `10.99.10.1` timeout.

Diagnostic :

```bash
# Côté VPS — UFW autorise-t-il bien 51821/udp ?
sudo ufw status verbose | grep 51821

# Le socket UDP est-il bien lié ?
sudo ss -ulnp | grep 51821

# Capture pour voir si le paquet arrive
sudo tcpdump -ni any udp port 51821 -c 10
# Lancer en parallèle un `sudo wg-quick down homelab && sudo wg-quick up homelab`
# côté laptop — un paquet handshake (~150 octets) doit apparaître.
```

- Si **0 paquet capturé** côté VPS → pare-feu en amont (ISP local du laptop, NAT mobile, ou record DNS qui ne pointe pas sur le VPS). Vérifier `dig +short wg-hub.ldesfontaine.com`.
- Si **paquet arrive mais aucun handshake retour** → mismatch de clé. Vérifier que la pubkey VPS dans la conf client correspond exactement à `sudo cat /etc/wireguard/wg-admin.pub` (sans espaces, sans retours ligne en trop).
- Si **handshake côté VPS mais pas reflété côté client** → `AllowedIPs` mal configuré côté client (doit inclure `10.99.10.0/24`).

### 10.2. Tunnel up mais ping `10.99.10.1` timeout

Diagnostic :

```bash
# Côté VPS — forwarding actif ?
sysctl net.ipv4.ip_forward
# Doit retourner 1.

# Règles iptables FORWARD posées par le PostUp ?
sudo iptables -L FORWARD -n -v | grep wg-admin
# Doit montrer deux règles ACCEPT (in + out).
```

Si forwarding à 0 → `sudo sysctl -p /etc/sysctl.d/99-wireguard-forward.conf` puis re-tester. Si toujours pas : le fichier sysctl.d a été supprimé, rejouer Ansible.

### 10.3. Mismatch privkey / pubkey vault

Symptôme : un peer apparaît dans `wg show` mais aucun handshake ne s'établit jamais, même réseau OK.

Cause typique : la pubkey dans le vault ne correspond pas à la privkey utilisée par le client (oubli de regénérer, copie tronquée, etc.).

Fix :

```bash
# Côté client — vérifier la pubkey dérivée de la privkey locale
wg pubkey < ~/.config/wireguard/homelab/laptop-priv.key

# Comparer avec la valeur du vault
ansible-vault view ansible/inventory/group_vars/vps/vault.yml | grep vault_wg_peer_laptop_pubkey
```

Les deux doivent matcher exactement. Sinon : ré-éditer le vault, rejouer le rôle, redistribuer.

### 10.4. Un restart Ansible coupe ma session WG en cours

Comportement attendu : le handler `Restarting wireguard hub` (`systemctl restart wg-quick@wg-admin`) recrée l'interface, ce qui drop les sessions en cours pendant 2-3 secondes. Les peers reconnectent automatiquement (handshake KeepAlive 25s).

Mitigation :
- Rejouer Ansible depuis une session SSH directe (sans passer par le tunnel WG).
- Ou utiliser `--tags wg_admin_hub --check` d'abord pour vérifier qu'il n'y a pas de changement à appliquer (`changed=0` → safe à skipper).

### 10.5. `systemctl status wg-quick@wg-admin` en `failed`

Diagnostic :

```bash
sudo journalctl -u wg-quick@wg-admin -n 50 --no-pager
```

Cas typiques :
- `wg: Key is not the correct length or format` → la privkey sur disque est corrompue. Vérifier `sudo wc -c /etc/wireguard/wg-admin.key` (doit être 45 octets = 44 base64 + `\n`). Si corruption, **avant de supprimer**, sauvegarder la pubkey actuelle (`sudo cat /etc/wireguard/wg-admin.pub`) — la suppression force la régénération, ce qui invalide la pubkey diffusée aux clients.
- `RTNETLINK answers: Operation not supported` → module kernel WireGuard absent. Sur Trixie, devrait être présent (`lsmod | grep wireguard`). Sinon `sudo modprobe wireguard`.
- `Address already in use: 51821` → un autre process écoute déjà sur 51821. `sudo ss -ulnp | grep 51821` pour identifier.

### 10.6. Le QR code phone ne scanne pas

Symptômes :
- Terminal trop petit → QR coupé. Maximiser la fenêtre, ou utiliser `qrencode -t UTF8` (caractères plus compacts).
- Thème terminal sombre + caractères Unicode mal rendus → essayer `qrencode -t ANSI` (caractères ASCII) ou exporter en PNG :
  ```bash
  qrencode -o /tmp/phone-qr.png < ~/.config/wireguard/homelab/phone.conf
  xdg-open /tmp/phone-qr.png
  # Penser à `shred -u /tmp/phone-qr.png` après import sur le phone.
  ```

### 10.7. FAIL au `--check` sur `Enforce 0600 perms` / `Read the WireGuard private key`

Symptôme : le pré-vol en `--check` plante sur l'une des tasks :

```
TASK [wg_admin_hub : Enforce 0600 perms on the WireGuard private key]
FAILED: file (/etc/wireguard/wg-admin.key) is absent, cannot continue
```

(ou bien plus loin, sur `Read the WireGuard private key` avec un slurp qui échoue.)

Cause : la task précédente `Generate the WireGuard private key (only if absent)` utilise `creates:` — en check mode elle simule sans écrire le fichier, et toutes les tasks suivantes qui exigent la présence physique de `/etc/wireguard/wg-admin.key` plantent. Limitation Ansible connue (cf. §1.5 et ADR-000 "Limite acceptée — check mode partiel").

Fix : au **premier** déploiement, ne pas lancer `--check`. Lancer directement le run réel de la section 2. À partir du 2ème run, la privkey existe sur disque et `--check` passe proprement.

---

## 11. Rollback

### 11.1. Désactiver temporairement le hub sans toucher au reste

```bash
ssh -p 2203 deploy@<ip-vps>
sudo systemctl disable --now wg-quick@wg-admin
sudo ufw delete allow 51821/udp
```

Le service est down, le port fermé, tout le reste (Pangolin, CrowdSec, portfolio) continue normalement.

### 11.2. Désinstallation complète

```bash
ssh -p 2203 deploy@<ip-vps>
sudo systemctl disable --now wg-quick@wg-admin
sudo rm -f /etc/wireguard/wg-admin.{conf,key,pub}
sudo rm -f /etc/sysctl.d/99-wireguard-forward.conf
sudo sysctl --system
sudo ufw delete allow 51821/udp
# Optionnel — désinstaller le paquet si plus aucun autre usage WG
sudo apt remove wireguard
```

Côté git :

```bash
git revert <sha-session-6-commits>
# Le rôle disparaît du playbook → run suivant : skip silencieux (tag wg_admin_hub
# matche zéro rôle).
```

### 11.3. Rotation de la privkey VPS (cas compromission)

```bash
# Côté VPS — sauvegarder l'ancienne pubkey pour pouvoir comparer
sudo cp /etc/wireguard/wg-admin.pub /etc/wireguard/wg-admin.pub.old

# Supprimer la privkey — le prochain run Ansible la régénérera
sudo rm /etc/wireguard/wg-admin.key

# Côté laptop — rejouer Ansible
cd ansible
ansible-playbook -i inventory/00-static.yml playbooks/deploy-vps-services.yml \
  --tags wg_admin_hub --diff
```

La nouvelle pubkey s'affiche en sortie de run. **Mettre à jour les fichiers `.conf` clients** (`PublicKey = ...` section `[Peer]`) avec la nouvelle valeur, puis `wg-quick down / up` côté chaque client.

---

## 12. Limites connues — reportées aux sessions suivantes

- **Dashboard Pangolin via tunnel admin** : architecture Host-aware (check du `Host` header + CSRF/cookies liés au FQDN) incompatible avec un accès IP+port direct, que ce soit via WG ou SSH tunnel. Limitation acceptée pour la session 6, résolution prévue en phase 11 (Authentik OIDC + exposition publique de `pangolin.ldesfontaine.com`). Voir §7.2 et [ADR-003](../adr/ADR-003-services-host-aware-vs-ip-friendly.md).
- **`net.ipv4.ip_forward` — résolu (2026-05-17)** : `devsec.hardening` pose `= 0` par défaut, `wg_admin_hub` et Docker (DNAT vers containers) requièrent `= 1`. Le `PostUp` de `wg-quick` ne suffit pas : il ne se rejoue pas quand l'interface est déjà up, donc chaque run de `harden.yml` ramenait l'host à `0` au runtime → incident production 2026-05-17 (portfolio inaccessible ~1h, containers up et UFW OK mais forwarding kernel disabled). **Fix** : override explicite dans `hardening_sysctl_overrides` (rôle `hardening`, [defaults/main.yml](../../ansible/roles/hardening/defaults/main.yml)) qui pose `net.ipv4.ip_forward: 1` via la variable `sysctl_overwrite` de `devsec.hardening.os_hardening`. La baseline devsec est ainsi pilotée dès le run hardening, pas en postlude — idempotence stricte garantie, plus de course entre rôles.
- **Pas de PresharedKey** : aujourd'hui, seule la paire de clés WG protège chaque peer. À ajouter si modèle de menace évolue (compromission d'un device client).
- **Pas de tunnel full** : split-tunnel uniquement (`AllowedIPs = 10.99.10.0/24` côté client). Pas de NAT sortant sur le hub.
- **Pas de monitoring/alerting** : pas de notification si l'unit `wg-quick@wg-admin` plante au boot. À câbler quand monitoring sera en place (Grafana/Loki ou alertmanager).
- **Pas de rotation automatique des clés** : opération manuelle (section 11.3).
- **Aucune restriction de port destination dans le tunnel** : une fois connecté au hub, le client peut atteindre n'importe quoi sur `10.99.10.1` (et tous les services hôte). Acceptable car le hub n'est ouvert qu'à un nombre limité de peers admin (Lucas). Si on partage à d'autres admins plus tard, segmenter via iptables FORWARD spécifiques.

---

## 13. Journal d'exécution

| Date | Opérateur | `changed=` (wg_admin_hub) | Tunnel laptop OK ? | Tunnel phone OK ? | Notes |
|---|---|---|---|---|---|
| 2026-05-17 | `ldesfontaine` | `changed=0` final sur les 2 playbooks | ✅ (38 KiB échangés) | ✅ (1.99 KiB échangés) | Dashboard Pangolin reporté phase 11 (Host-aware, cf. §7.2 + ADR-003). |
