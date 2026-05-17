# Runbook — Session 2 : Hardening lourd du VPS

> **Statut** : actif — v1.0 — auteur `ldesfontaine`
> **Référence** : `docs/adr/ADR-000-fondations-ansible.md` (Décision 5)
> **Playbook** : `ansible/playbooks/harden.yml`

Objectif de la session : monter le niveau de sécurité du VPS post-bootstrap via la collection `devsec.hardening` (sysctl/kernel/login.defs/PAM + ciphers/KEX/MACs SSH modernes), activer les updates auto stricts Debian-Security, déployer fail2ban avec une jail sshd sur le port custom, et poser un banner légal sur `/etc/issue.net`.

---

## 1. Prérequis

- VPS bootstrappé via `playbooks/bootstrap.yml` (session 1) — `ssh -p 2203 deploy@<ip>` fonctionne sans password, sudo NOPASSWD.
- `ssh-agent` actif sur le poste de pilotage, clé `~/.ssh/id_ed25519_homelab` chargée (`ssh-add -l` la liste).
- Console KVM Hetzner accessible (web) — voie de récupération si la nouvelle conf sshd casse l'accès.
- Le mot de passe vault est disponible (`~/.ansible/vault-pass-homelab.txt` lisible).
- Collections requises installées :

  ```bash
  cd ansible
  ansible-galaxy collection install -r requirements.yml
  ```

  En particulier `devsec.hardening` ≥ 10.0.0 doit être présent :

  ```bash
  ansible-galaxy collection list devsec.hardening
  ```

- L'IP de pilotage (laptop) est, si possible, ajoutée à `fail2ban_ignoreip` dans `group_vars/vps/vars.yml` (sinon : tu peux te bannir toi-même en cas de retry SSH foireux).

## 2. Validation pré-vol (locale, ne touche pas au VPS au-delà du ping)

```bash
cd ansible

# Syntaxe + lint
ansible-playbook playbooks/harden.yml --syntax-check
ansible-lint
yamllint -c ../.yamllint .

# Ping en credentials cibles
ansible -i inventory vps-pangolin -m ping
```

Le ping doit retourner `pong`. S'il échoue : vérifier détection SSH (`_detect-ssh.yml` doit basculer sur `deploy@2203`), connectivité réseau, état du firewall.

## 3. Procédure d'exécution

### 3.1. Syntax check

```bash
cd ansible
ansible-playbook playbooks/harden.yml --syntax-check
```

Aucune erreur attendue.

### 3.2. Dry-run

```bash
cd ansible
ansible-playbook playbooks/harden.yml --check --diff
```

⚠️ **Limite connue identique au bootstrap (ADR-000 Décision 4)** : `devsec.hardening.ssh_hardening` chaîne plusieurs tasks dépendantes d'un état créé en runtime (génération hostkeys, validation `sshd -t` du drop-in), et certaines vérifications (`ssh -V`, `package_facts`) peuvent retourner des états incohérents en `--check`. Le dry-run peut donc planter au milieu — c'est attendu. Lire le diff de tout ce qui passe (banner, jail.local, 50unattended-upgrades) ; pour le reste, se fier à l'idempotence post-run.

### 3.3. Run réel

```bash
cd ansible
ansible-playbook playbooks/harden.yml
```

Pendant le run, le moment critique est le reload sshd à la fin de `devsec.hardening.ssh_hardening` : le drop-in `/etc/ssh/sshd_config.d/99-hardening.conf` est validé via `sshd -t` avant reload (le handler devsec). Si la validation échoue, sshd n'est PAS rechargé — l'ancienne conf reste active, on a le temps de corriger.

## 4. Post-run validation

### 4.1. Connexion humaine (CRITIQUE)

Depuis le laptop, **AVANT de fermer la session SSH actuelle** :

```bash
# Nouvelle session sur le port cible
ssh -p 2203 deploy@<ip>
```

Doit aboutir et afficher le banner légal `/etc/issue.net` avant le prompt de connexion. Si **KO** → ne pas couper la session admin existante, passer en rollback (§5).

### 4.2. Banner

```bash
ssh -p 2203 deploy@<ip> 'cat /etc/issue.net'
```

Doit contenir « AUTHORIZED ACCESS ONLY » et le domaine `ldesfontaine.com` interpolé.

### 4.3. Configuration sshd effective

```bash
ssh -p 2203 deploy@<ip> 'sudo sshd -T | grep -iE "^(port|allowusers|banner|ciphers|kexalgorithms|macs|loginGracetime|maxstartups|authenticationmethods|passwordauthentication|permitrootlogin) "'
```

Attendu :

- `port 2203`
- `allowusers deploy`
- `banner /etc/issue.net`
- `passwordauthentication no`
- `permitrootlogin no`
- `authenticationmethods publickey`
- `ciphers`/`macs`/`kexalgorithms` durcis (algorithmes modernes uniquement — pas de `aes128-cbc`, pas de `hmac-sha1`, pas de `diffie-hellman-group1-sha1`)
- `loginGracetime 30`
- `maxstartups 10:30:60`

#### AllowTcpForwarding — exception ciblée pour `deploy`

Baseline devsec : `AllowTcpForwarding no` globalement. Le rôle `hardening` pose un drop-in supplémentaire `/etc/ssh/sshd_config.d/99-tcp-forwarding-users.conf` qui réactive le forwarding via un bloc `Match User` pour les users listés dans `hardening_ssh_tcp_forwarding_users` (par défaut : `[deploy]`). Vérification :

```bash
# Globalement : forwarding interdit
ssh -p 2203 deploy@<ip> 'sudo sshd -T | grep -i allowtcpforwarding'
# Attendu : allowtcpforwarding no

# Pour le user deploy : forwarding autorisé (Match override)
ssh -p 2203 deploy@<ip> 'sudo sshd -T -C user=deploy,host=localhost,addr=127.0.0.1 | grep -i allowtcpforwarding'
# Attendu : allowtcpforwarding yes

# Test bout-en-bout — SSH tunnel vers une socket arbitraire (port 22 de localhost)
ssh -p 2203 -L 12222:127.0.0.1:22 -N -f deploy@<ip>
nc -zv localhost 12222   # doit répondre "succeeded"
pkill -f 'ssh -p 2203 -L 12222'
```

Cas d'usage immédiat (session 6+) : `ssh -p 2203 -L 3000:127.0.0.1:3000 deploy@<ip>` pour atteindre le dashboard Pangolin via `http://localhost:3000` depuis le laptop (Pangolin route par Host header en interne — l'accès "IP+port direct" ne fonctionne pas avec lui tant qu'Authentik + reverse proxy interne ne sont pas en place).

Pour fermer cette exception (cas de rollback ou quand Authentik prend le relais), passer `hardening_ssh_tcp_forwarding_users: []` en override et rejouer — le drop-in est supprimé, baseline devsec restaurée.

### 4.4. fail2ban

```bash
ssh -p 2203 deploy@<ip> 'sudo systemctl is-active fail2ban && sudo fail2ban-client status sshd'
```

Attendu : `active`, puis status indiquant la jail `sshd` active, backend `systemd`, currently banned `0`.

### 4.5. unattended-upgrades

```bash
ssh -p 2203 deploy@<ip> 'sudo systemctl is-active unattended-upgrades && \
  grep -E "(Origins-Pattern|Automatic-Reboot)" /etc/apt/apt.conf.d/50unattended-upgrades'
```

Attendu : service `active`, ligne `origin=Debian,codename=${distro_codename},label=Debian-Security`, `Automatic-Reboot "false"`.

Vérifier que les timers APT sont actifs :

```bash
ssh -p 2203 deploy@<ip> 'systemctl list-timers apt-daily.timer apt-daily-upgrade.timer --no-pager'
```

### 4.6. sysctl durci

```bash
ssh -p 2203 deploy@<ip> 'sudo sysctl kernel.kptr_restrict kernel.yama.ptrace_scope net.ipv4.ip_forward net.ipv6.conf.all.disable_ipv6'
```

Attendu : `kernel.kptr_restrict = 2`, `kernel.yama.ptrace_scope = 1`, `net.ipv4.ip_forward = 1` (exception explicite, cf. §6 — Docker DNAT + wg-admin), `net.ipv6.conf.all.disable_ipv6 = 0` (IPv6 reste activé).

#### Exception sysctl — `net.ipv4.ip_forward = 1`

Le rôle `hardening` override la baseline devsec via `hardening_sysctl_overrides` (cf. [defaults/main.yml](../../ansible/roles/hardening/defaults/main.yml)) pour forcer `net.ipv4.ip_forward: 1`. Justification :

- **Docker** : sans IP forwarding, la chaîne `nat/PREROUTING` (DNAT vers les containers exposés par Pangolin et publiés via `ufw-docker allow`) est inopérante. Symptôme : containers up + UFW OK + ports en écoute, mais aucun trafic externe ne joint un service publié.
- **wg-admin** : le hub WireGuard route les paquets entre peers admin et le subnet `10.99.10.0/24`. Sans `ip_forward=1`, le forwarding kernel bloque tous les paquets traversants.

Le `PostUp` de `wg-quick@wg-admin` pose aussi `sysctl -w net.ipv4.ip_forward=1` mais **ne se rejoue pas** quand l'interface est déjà up. Sans l'override du rôle hardening, chaque run de `harden.yml` ramenait l'host à `0` au runtime → incident production 2026-05-17 (portfolio inaccessible ~1h). L'override garantit que c'est la valeur définitive posée par `devsec.hardening.os_hardening` lui-même, idempotente, persistée dans `/etc/sysctl.d/`.

### 4.7. Idempotence (le test qui valide vraiment la session)

```bash
cd ansible
ansible-playbook playbooks/harden.yml
```

Attendu dans le récap : `changed=0` sur l'host VPS. Si ce n'est pas le cas, identifier le module non-idempotent — possible que devsec déclenche un changement cosmétique sur les hostkeys ou les moduli ; trancher avec l'utilisateur avant tout merge.

## 5. Rollback manuel

### 5.1. SSH cassé après reload sshd

Si la nouvelle conf sshd refuse les connexions (lockout) :

1. **Garder la session SSH actuelle ouverte si elle l'est encore** — c'est la voie la plus rapide.
2. Sinon, ouvrir la **console KVM Hetzner** (web) et login `root` (mode rescue si besoin).
3. Supprimer le drop-in hardening :

   ```bash
   ls -la /etc/ssh/sshd_config.d/
   # Le drop-in fait par devsec est /etc/ssh/sshd_config.d/99-hardening.conf
   # Backup éventuel : 99-hardening.conf.XXXX.bak
   mv /etc/ssh/sshd_config.d/99-hardening.conf{,.disabled}
   sshd -t      # validation du sshd_config principal seul
   systemctl reload ssh
   ```

4. Vérifier la connexion : `ssh -p 2203 deploy@<ip>` doit refonctionner (puisque le sshd_config principal posé par bootstrap est intact).
5. Identifier la cause (algorithme client incompatible, AllowUsers écrasé, etc.), corriger côté Ansible, retenter.

### 5.2. fail2ban a banni l'IP de pilotage

```bash
# Via console Hetzner ou depuis une autre IP
sudo fail2ban-client status sshd                  # voir les IPs bannies
sudo fail2ban-client unban <ip-bannie>
```

Ajouter l'IP de pilotage à `fail2ban_ignoreip` dans `group_vars/vps/vars.yml` puis rejouer le rôle :

```bash
ansible-playbook playbooks/harden.yml --tags fail2ban
```

### 5.3. unattended-upgrades cassé (timer qui boucle, dépendances cassées)

```bash
# Désactiver les upgrades auto
sudo systemctl disable --now unattended-upgrades apt-daily-upgrade.timer
# Restaurer un periodic config vide
sudo mv /etc/apt/apt.conf.d/20auto-upgrades{,.disabled}
```

Et plus tard, après diagnostic, rejouer `playbooks/harden.yml --tags unattended-upgrades`.

### 5.4. Banner cassant un client SFTP/automation

Le banner s'affiche AVANT l'auth — la plupart des clients SSH/SFTP scriptés le tolèrent, mais certains MUAs ou tooling minimaliste peuvent paniquer. Désactiver côté sshd via override dans `group_vars/vps/vars.yml` :

```yaml
ssh_banner: false
```

Puis rejouer le rôle `hardening` avec le tag `hardening-ssh`.

## 6. Limites connues — explicitement reportées aux sessions suivantes

- **Pas de Docker** : sera installé via un rôle dédié en session 3 (Décision 6).
- **Pas de Pangolin** : session 4. Le port 80/443 reste fermé par UFW.
- **Pas de CrowdSec** : session 5. fail2ban joue son rôle en attendant (couche brute-force SSH).
- **Pas de bouncer CrowdSec** : viendra avec la stack Pangolin.
- **Pas de mail MTA** : `unattended_upgrades_mail` reste vide. Les rapports finissent dans `/var/log/unattended-upgrades/`. À reconnecter quand on aura un MTA (msmtp) ou une cible Pushover/Telegram.
- **devsec.hardening pose `MaxAuthTries 2`** dans son drop-in, mais le `sshd_config` principal du bootstrap a `MaxAuthTries 3` qui prend la priorité (sshd : « first value wins »). Acceptable mais à harmoniser ultérieurement si on veut le 2 strict de devsec.
- **`AllowTcpForwarding yes` pour `deploy`** (drop-in `99-tcp-forwarding-users.conf`) est une **exception ouverte de la baseline durcie**. Indispensable aujourd'hui pour atteindre le dashboard Pangolin via `ssh -L 3000:127.0.0.1:3000`. À retirer (`hardening_ssh_tcp_forwarding_users: []`) le jour où Authentik + reverse proxy interne permettront l'accès au dashboard via FQDN sans tunnel. Aucun autre user n'a cette permission — `Match User deploy` est la seule porte.

## 7. Journal d'exécution

À remplir au moment du run :

| Date | Opérateur | Host | Résultat | Notes |
|---|---|---|---|---|
| | `ldesfontaine` | `vps-pangolin` | | |
