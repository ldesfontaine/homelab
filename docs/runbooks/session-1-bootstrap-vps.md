# Runbook — Session 1 : Bootstrap VPS Hetzner

> **Statut** : actif — v1.0 — auteur `ldesfontaine`
> **Référence** : `docs/adr/ADR-000-fondations-ansible.md` (Décisions 2 et 4)
> **Playbook** : `ansible/playbooks/bootstrap.yml`

Objectif de la session : prendre un VPS Hetzner Debian 13 fraîchement provisionné, créer un user `deploy` avec sudo NOPASSWD et clé SSH, durcir sshd, basculer le port SSH de 22 vers 2203, configurer la base OS (timezone Europe/Paris, locale, NTP chrony, paquets essentiels).

---

## 1. Prérequis

- VPS Hetzner provisionné manuellement (Décision 1) avec Debian 13 (Trixie) propre.
- Lors de la création, la clé publique SSH admin a été déposée dans `/root/.ssh/authorized_keys` via l'option "SSH keys" de la console Hetzner.
- L'IP publique du VPS est renseignée dans `ansible/inventory/00-static.yml` (`ansible_host` du host `vps-pangolin`).
- L'accès console Hetzner (web KVM) est confirmé fonctionnel — c'est la voie de récupération en cas de lockout.
- Le mot de passe vault est en place : `~/.ansible/vault-pass-homelab.txt` lisible, `ansible-vault view ansible/inventory/group_vars/vps/vault.yml` renvoie le contenu déchiffré.
- Le poste de pilotage peut joindre le port 22 du VPS (test depuis le laptop : `nc -vz <ip> 22`).
- Les collections requises sont installées : `ansible-galaxy collection install -r ansible/requirements.yml`.

## 2. Validation pré-vol (locale, ne touche pas au VPS au-delà du ping)

```bash
cd ansible

# Lint et syntax
ansible-playbook playbooks/bootstrap.yml --syntax-check
ansible-lint
yamllint -c ../.yamllint .

# Ping en credentials bootstrap (root@22) — preuve que le VPS répond et que la clé est en place
ansible -i inventory vps-pangolin -m ping \
  -e "ansible_port=22 ansible_user=root"
```

Le ping doit retourner `pong`. S'il échoue : vérifier IP, clé SSH, firewall amont Hetzner.

## 3. Procédure d'exécution

### 3.1. Syntax check

```bash
cd ansible
ansible-playbook playbooks/bootstrap.yml --syntax-check
```

Aucune erreur attendue.

### 3.2. Dry-run

⚠️ La détection auto trouvera le port 22 ouvert mais PAS le 2203 (puisqu'on n'a pas encore bootstrapé). On force donc les credentials bootstrap :

```bash
cd ansible
ansible-playbook playbooks/bootstrap.yml --check --diff \
  -e "ansible_port=22 ansible_user=root"
```

Lire le diff : le template sshd_config et les fichiers locale/chrony doivent montrer les changements attendus. Aucune surprise (création utilisateur, règles UFW, etc.).

### 3.3. Run réel

```bash
cd ansible
ansible-playbook playbooks/bootstrap.yml
```

Pas besoin d'extra-vars : `_detect-ssh.yml` voit que 2203 est fermé et bascule automatiquement sur `root@22`.

Pendant le run, le moment critique est l'étape `05-validate-and-switch` : Ansible coupe sa connexion `root@22`, en rouvre une `deploy@2203`, et fait un ping. Si ça passe, l'étape `06-close-bootstrap-port` ferme le 22.

## 4. Post-run validation

### 4.1. Connexion humaine

Depuis le laptop :

```bash
ssh -p 2203 deploy@<ip>           # doit fonctionner (clé SSH)
ssh -p 22  root@<ip>              # doit échouer (port fermé par UFW + AllowUsers exclu root)
```

### 4.2. Firewall

```bash
ssh -p 2203 deploy@<ip> 'sudo ufw status verbose'
```

Attendu : `Status: active`, default deny incoming / allow outgoing, **port 2203/tcp ALLOW**, **aucune ligne pour port 22**.

### 4.3. Services système

```bash
ssh -p 2203 deploy@<ip> 'sudo systemctl is-active ssh chrony && timedatectl'
```

Attendu : `active` pour les deux, `Time zone: Europe/Paris`, `System clock synchronized: yes`, `NTP service: active`.

### 4.4. Locale et paquets

```bash
ssh -p 2203 deploy@<ip> 'locale | head -3 && command -v jq htop vim'
```

Attendu : `LANG=en_US.UTF-8`, et les binaires installés.

### 4.5. Idempotence (le test qui valide vraiment le rôle)

```bash
cd ansible
ansible-playbook playbooks/bootstrap.yml
```

Attendu dans le récap : `changed=0` sur l'host VPS. Si ce n'est pas le cas, identifier le module non-idempotent et corriger avant tout merge.

## 5. Rollback manuel via console Hetzner

En cas de lockout (la bascule `04 → 05` échoue, ou sshd refuse les connexions sur 2203 après reload) :

1. **Ouvrir la console KVM Hetzner** (web). Login `root` avec le password initial du provisioning (à demander à Hetzner si non noté), ou via mode rescue si la console root ne fonctionne pas.
2. **Restaurer sshd_config** :
   ```bash
   ls -la /etc/ssh/sshd_config*.bak
   # le module template crée /etc/ssh/sshd_config.XXXX.bak juste avant l'écriture
   cp /etc/ssh/sshd_config.<timestamp>.<rand>.bak /etc/ssh/sshd_config
   sshd -t   # validation
   systemctl reload ssh
   ```
3. **Rouvrir le port 22 dans UFW** (si UFW a déjà été activé) :
   ```bash
   ufw allow 22/tcp comment 'SSH bootstrap (rollback)'
   ufw status
   ```
4. **(Si nécessaire) ré-autoriser root par SSH temporairement** : éditer `/etc/ssh/sshd_config`, mettre `PermitRootLogin yes` et `AllowUsers root deploy`, `systemctl reload ssh`. **À retirer immédiatement après diagnostic.**
5. Identifier la cause du lockout (clé SSH absente de `~deploy/.ssh/authorized_keys`, perms `.ssh` mauvaises, etc.), corriger côté Ansible, retenter.

## 6. Limites connues — explicitement reportées aux sessions suivantes

- **Pas de hardening lourd sshd** : ciphers, KEX, MACs au défaut Debian Trixie. À traiter en session 2 via `devsec.hardening` (Décision 5).
- **Pas de fail2ban** : protection brute-force absente. À ajouter en session 2 ou 3 selon priorisation.
- **Pas d'unattended-upgrades** : security updates pas encore automatisés. Session 2.
- **Pas de Docker** : sera installé via un rôle dédié en session 3 (Décision 6).
- **Pas de CrowdSec, pas de Pangolin** : sessions ultérieures (cf. cahier).
- **`AllowUsers deploy`** est restrictif : ajouter d'autres users SSH ultérieurement nécessitera d'override `bootstrap_sshd_*` ou de switcher vers la conf devsec.

## 7. Journal d'exécution

À remplir au moment du run :

| Date | Opérateur | Host | Résultat | Notes |
|---|---|---|---|---|
| | `ldesfontaine` | `vps-pangolin` | | |
