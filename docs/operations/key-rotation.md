# Procédures de rotation des secrets

> **Statut** : actif — première procédure documentée : rotation
> complète des clés WireGuard admin. Autres procédures à étoffer
> au fur et à mesure des rotations effectives.
> **Auteur** : `ldesfontaine`

Ce document regroupera les procédures pas-à-pas de rotation pour
chaque type de secret du homelab. À étoffer au moment de chaque
rotation effective : c'est ce qu'on fait qu'on documente, pas ce
qu'on imagine faire.

## Secrets concernés

Inventaire complet dans [`../secrets-inventory.md`](../secrets-inventory.md).

- Clés WireGuard admin (hub VPS + peers laptop/phone) — premier
  full rotate documenté au Lot suivant.
- Clé SSH `id_ed25519_homelab` — rotation à chaque compromission
  potentielle de la machine de pilotage.
- Vault password Ansible — rotation annuelle ou sur compromission
  gestionnaire de mots de passe.
- Token Cloudflare API — rotation annuelle.
- Token GHCR — rotation annuelle.
- Secrets applicatifs (Payload, Pangolin admin, etc.) — selon
  doctrine de chaque service.

## Procédures (à venir)

- [x] [Rotation full des clés WireGuard admin (hub + tous peers)](#rotation-full-des-clés-wireguard-admin)
- [ ] Rotation clé SSH `id_ed25519_homelab`
- [ ] Rotation vault password Ansible
- [ ] Rotation token Cloudflare API
- [ ] Rotation token GHCR

## Principes généraux

Voir [project-overview §11](../00-project-overview.md) et
[ADR-000 Décision 8](../adr/ADR-000-fondations-ansible.md).

## Rotation full des clés WireGuard admin

### Objet

Régénérer entièrement les clés WireGuard du tunnel admin
(WG-ADMIN-RELAY) : privkey + pubkey du hub côté VPS, privkeys +
pubkeys de **tous** les peers actifs (laptop, phone, et tout futur
peer déclaré dans `scripts/wg-admin-profiles.yml`). À l'issue de
la procédure, aucune ancienne valeur de clé n'est encore en usage.

Cette rotation traite indistinctement tous les peers, sans
distinction de motif. Pour révoquer un peer compromis sans
toucher aux autres, voir la section future « Révocation d'un peer
WG individuel » (à documenter au moment du besoin).

### Quand l'exécuter

- **Annuelle** — bonne hygiène cryptographique, indépendamment de
  toute compromission supposée.
- **Compromission d'un device peer** — laptop ou phone volé,
  appartenant à un proche ayant accès non révoqué, etc. Même si
  un seul peer est concerné, la doctrine actuelle préfère un
  roulement complet plutôt qu'une révocation ciblée, pour éviter
  un état asymétrique entre peers.
- **Mise en place initiale post-déploiement** — repartir clean
  une fois que le tunnel est validé fonctionnellement, pour que
  les clés de test ne survivent pas en prod.
- **Changement majeur du modèle de menace** — exposition publique
  de la pubkey hub élargie, ouverture du repo à d'autres
  contributeurs, etc.

### Stratégie : bascule franche

La rotation se fait en mode « bascule franche » : on supprime
l'ancien, on installe le nouveau, on teste. Pas de coexistence
des deux états.

**Couverture pendant la fenêtre sans tunnel WG admin** : la
machine de pilotage (laptop) garde l'accès SSH direct au VPS sur
le port 2203 — c'est la voie de récupération canonique du repo
(cf. ADR-002 et doctrine SSH direct). Le tunnel WG admin n'est
PAS la seule voie d'accès au VPS, donc la fenêtre de quelques
minutes pendant la rotation n'est pas un risque opérationnel.

Une stratégie « coexistence » (ajouter le nouveau peer à côté de
l'ancien, tester, retirer l'ancien) est plus complexe à exécuter
et à rollbacker. Elle n'apporte de bénéfice que si SSH direct
n'est plus disponible — ce qui n'est pas notre cas.

### Prérequis

- SSH direct au VPS confirmé fonctionnel :
  `ssh -p 2203 deploy@<ip-vps>` répond sans tunnel WG actif.
- `ssh-agent` chargé avec `~/.ssh/id_ed25519_homelab`.
- Vault password file en place : `~/.ansible/vault-pass-homelab.txt`
  lisible.
- Clé age maître en place : `~/.age/homelab.key` (`0600`) — pour
  l'archive `.tar.gz.age` finale.
- Cloud chiffré privé pour l'archive : déjà setup avec la pubkey
  age correspondante (cf. ci-dessous).
- Console KVM Hetzner accessible — voie de récupération ultime si
  même SSH direct cassait pendant la rotation (très improbable).

### Cloud chiffré privé — endroit pour l'archive `.tar.gz.age`

L'archive `~/homelab/keys/wg-admin-relay.tar.gz.age` (~quelques Ko)
contient les nouvelles privkeys peers chiffrées par age. Elle doit
être stockée sur un endroit chiffré accessible depuis la machine
de pilotage, et survivre à une perte locale du laptop.

**Option actuelle (Lucas)** : Google Drive — cf.
[`../wg-admin-profiles.md`](../wg-admin-profiles.md) § « Sécurité ».
L'archive y est uploadée manuellement après chaque rotation.

**Alternatives recommandées** (à considérer si Google Drive ne
convient plus) :

- **Cryptomator + Drive/Dropbox/iCloud** : vault Cryptomator
  chiffré par-dessus un cloud existant. Avantage : double
  chiffrement (Cryptomator + age), passphrase indépendante du
  compte cloud.
- **rclone vers Backblaze B2 avec `--crypt` remote** : low-cost
  long terme (B2 facture au volume, négligeable pour quelques
  Ko), versioning serveur, contrôle total des clés.
- **Bitwarden Send** : `bw send create --file ...` — limite 100 MB,
  expiration max 31 jours. À renouveler à chaque rotation, mais
  simple si Bitwarden est déjà utilisé pour le gestionnaire de
  mots de passe principal.

Le choix dépend du compromis simplicité / contrôle / coût. Tant
que le format reste `.tar.gz.age`, le déchiffrement local est
identique : `age -d -i ~/.age/homelab.key`.

### Périmètre — fichiers et secrets touchés

Cette rotation modifie les éléments suivants :

| Élément | Type | Localisation |
|---|---|---|
| Privkeys peers (laptop, phone, ...) | secret | `~/homelab/keys/wg-admin-relay/*.key` (hors repo) |
| Pubkeys peers | public | `~/homelab/keys/wg-admin-relay/*.pub` (hors repo) + `ansible/inventory/group_vars/vps/vault.yml` (in-repo, chiffré) |
| Privkey hub | secret | `/etc/wireguard/wg-admin.key` (VPS uniquement) |
| Pubkey hub | public | `/etc/wireguard/wg-admin.pub` (VPS) + `scripts/wg-admin-profiles.yml` (in-repo, clair) + `docs/wg-admin-profiles.md` (in-repo, clair, table OPNsense peer) |
| Confs clients régénérées | secret | `~/homelab/keys/wg-admin-relay/profiles/*.conf` + `*.png` (hors repo) |
| Archive backup | secret | `~/homelab/keys/wg-admin-relay.tar.gz.age` (local + cloud chiffré) |

À l'issue de la rotation, 1 commit unique poussera le diff de :
- `ansible/inventory/group_vars/vps/vault.yml` (diff opaque, vault
  chiffré — Git voit juste qu'un blob a changé)
- `scripts/wg-admin-profiles.yml` (`hub.public_key` mise à jour)
- `docs/wg-admin-profiles.md` (table OPNsense peer, pubkey VPS hub)
- `docs/operations/key-rotation.md` (mise à jour du journal des
  rotations exécutées en fin de ce document)

### Procédure pas-à-pas

#### 1. Inventaire avant rotation

```bash
# Liste des peers déclarés
cd ~/homelab
.venv/bin/python scripts/wg-admin-gen-profile.py --list
```

```bash
# État actuel côté VPS
ssh -p 2203 deploy@<ip-vps> 'sudo wg show wg-admin'
```

Noter chaque peer avec sa pubkey actuelle, et la pubkey du hub. C'est
la « photo avant ». Doit matcher `scripts/wg-admin-profiles.yml` et
le vault.

#### 2. Backup de l'état actuel

```bash
BACKUP_DIR=~/homelab/rotation-backups/$(date +%Y%m%d-%H%M)
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# Backup des confs actuelles côté laptop
cp ~/.config/wireguard/homelab/*.{key,pub,conf} "$BACKUP_DIR/" 2>/dev/null || true

# Backup du vault avant modification — déchiffré, à supprimer après
# validation rotation OK. Méthode `view` (non destructive) plutôt que
# `decrypt` (qui modifie le fichier source si --output est mal géré).
ansible-vault view ansible/inventory/group_vars/vps/vault.yml \
  --vault-password-file ~/.ansible/vault-pass-homelab.txt \
  > "$BACKUP_DIR/vault-decrypted-backup.yml"
chmod 600 "$BACKUP_DIR/vault-decrypted-backup.yml"

ls -la "$BACKUP_DIR/"
```

> **⚠️ Sécurité** : `vault-decrypted-backup.yml` contient tous les
> secrets vault en clair. À `shred -u` immédiatement après
> validation que la rotation a fonctionné (étape 16).

#### 3. Génération des nouvelles privkeys peers (côté laptop)

```bash
cd ~/homelab/keys/wg-admin-relay
umask 077

# Pour chaque peer actif. La liste doit être dérivée de l'inventaire
# réel (sortie de `wg show wg-admin` côté VPS croisée avec les
# `vault_wg_peer_*` du vault), PAS codée en dur ici — elle évoluera
# avec le homelab.
# Exemple à date (laptop, phone, opnsense) :

for peer in laptop phone opnsense; do
  # Sauvegarder l'ancien (rollback)
  mv "${peer}-priv.key" "${peer}-priv.key.old" 2>/dev/null || true
  mv "${peer}.key" "${peer}.key.old" 2>/dev/null || true
  mv "${peer}-pub.key" "${peer}-pub.key.old" 2>/dev/null || true
  mv "${peer}.pub" "${peer}.pub.old" 2>/dev/null || true

  # Générer la nouvelle paire
  wg genkey | tee "${peer}.key" | wg pubkey > "${peer}.pub"
  chmod 600 "${peer}.key"
done

ls -la
# Les *.key DOIVENT être en 0600. Les *.pub en 0644.
```

> **Note** : adapter les noms de fichiers (`<peer>.key` vs
> `<peer>-priv.key`) à la convention existante dans le dossier. Le
> script `wg-admin-gen-profile.py` cherche `<peer>.key` (cf. son
> code source). Si ta convention historique utilise `-priv` /
> `-pub`, renommer en `.key` / `.pub` pour matcher le script.

#### 4. Mise à jour du vault Ansible

```bash
cd ~/homelab
ansible-vault edit ansible/inventory/group_vars/vps/vault.yml
```

Remplacer les valeurs de chaque `vault_wg_peer_<name>_pubkey` par
le contenu du `.pub` correspondant. Exemple pour deux peers :

```yaml
vault_wg_peer_laptop_pubkey: "<contenu de ~/homelab/keys/wg-admin-relay/laptop.pub>"
vault_wg_peer_phone_pubkey:  "<contenu de ~/homelab/keys/wg-admin-relay/phone.pub>"
```

Sauvegarder. Vérifier la cohérence :

```bash
cat ~/homelab/keys/wg-admin-relay/laptop.pub
cat ~/homelab/keys/wg-admin-relay/phone.pub
ansible -i ansible/inventory vps-pangolin \
  -m debug -a 'var=vault_wg_peer_laptop_pubkey'
# La valeur affichée doit matcher le contenu du .pub
```

#### 5. Suppression de la privkey hub côté VPS (force régénération)

```bash
ssh -p 2203 deploy@<ip-vps>
sudo cp /etc/wireguard/wg-admin.pub /etc/wireguard/wg-admin.pub.old
sudo rm /etc/wireguard/wg-admin.key
sudo systemctl stop wg-quick@wg-admin
exit
```

À cet instant :
- Le tunnel WG admin est down côté VPS.
- La privkey hub est supprimée — il n'y a aucun retour en arrière
  possible sur cette étape (la privkey n'est pas backupée, par
  doctrine ADR-000 : « la privkey ne quitte JAMAIS le VPS »).
- L'accès SSH direct sur 2203 reste opérationnel (couverture).

#### 6. Re-déploiement du rôle wg_admin_hub

```bash
cd <racine-repo>/ansible
../.venv/bin/ansible-playbook playbooks/deploy-vps-services.yml \
  --tags wg_admin_hub --diff
```

> **Note** : le venv vit à la racine du repo (`.venv/`), mais la
> commande se lance depuis le sous-dossier `ansible/`. D'où le
> `../.venv/bin/ansible-playbook` (et non `.venv/bin/...`). Adapter
> `<racine-repo>` au chemin local — la doctrine ne hardcode pas ce
> chemin, il dépend de l'installation.

Attendu :
- `changed > 0` sur les tasks « Generate the WireGuard private
  key », « Derive the WireGuard public key », « Persist the
  WireGuard public key to disk », « Deploy the WireGuard hub
  configuration ».
- Le handler `Restarting wireguard hub` se déclenche →
  `wg-quick@wg-admin` redémarre avec la nouvelle privkey.
- La task `Show client-side connection info` (ou debug
  équivalent) affiche la **nouvelle pubkey du hub**. La copier.

Vérification immédiate côté VPS :

```bash
ssh -p 2203 deploy@<ip-vps> 'sudo wg show wg-admin'
```

Attendu : interface up, listening port 51821, les peers déclarés
avec leurs nouvelles pubkeys (matchant le vault). Aucun handshake
encore — les clients ne sont pas reconfigurés.

#### 7. Récupération de la nouvelle pubkey hub (méthode alternative)

Si la pubkey n'a pas été capturée à l'étape 6, la lire
directement :

```bash
ssh -p 2203 deploy@<ip-vps> 'sudo cat /etc/wireguard/wg-admin.pub'
```

#### 8. Mise à jour de `scripts/wg-admin-profiles.yml`

Éditer le fichier, remplacer la valeur de `hub.public_key` par la
nouvelle pubkey hub. Vérifier le diff :

```bash
git diff scripts/wg-admin-profiles.yml
```

#### 9. Mise à jour de `docs/wg-admin-profiles.md`

Dans la section « Peer VPS-hub-pangolin » (table sous
« Configuration côté OPNsense (peer maison) »), remplacer la
ligne « Clé publique » par la nouvelle pubkey hub.

```bash
git diff docs/wg-admin-profiles.md
```

#### 10. Régénération des confs clients

```bash
cd ~/homelab
.venv/bin/python scripts/wg-admin-gen-profile.py --all
```

Output attendu : `~/homelab/keys/wg-admin-relay/profiles/laptop.conf`,
`phone.conf`, et leurs `.png` (QR codes).

Le script lit la pubkey hub depuis le yaml qu'on vient de mettre à
jour, et les privkeys peers depuis les nouveaux `<peer>.key`.

#### 11. Activation du tunnel laptop + test

Selon la méthode utilisée habituellement (NetworkManager ou
wg-quick) :

**Via NetworkManager (procédure standard)** :

```bash
# Supprimer l'ancienne connexion
sudo nmcli connection delete homelab 2>/dev/null || true

# Importer la nouvelle
nmcli connection import type wireguard \
  file ~/homelab/keys/wg-admin-relay/profiles/laptop.conf

# Renommer la connexion en "homelab" (convention projet)
nmcli connection modify wireguard-laptop connection.id homelab

# Activer
nmcli connection up homelab
```

**Via wg-quick (méthode alternative)** :

```bash
sudo wg-quick down homelab 2>/dev/null || true
sudo install -m 0600 -o root -g root \
  ~/homelab/keys/wg-admin-relay/profiles/laptop.conf \
  /etc/wireguard/homelab.conf
sudo wg-quick up homelab
```

> **⚠️ Piège connu — ne pas tester le tunnel admin depuis le LAN
> maison.** Le tunnel admin a `AllowedIPs` couvrant `10.10.10.0/24`
> et les autres VLANs internes. Activé depuis le LAN maison, il
> capture le trafic vers ces subnets et le route vers le VPS au
> lieu du LAN direct — conflit de routes.
>
> Conséquence si le tunnel OPNsense est down : le DNS interne
> (`10.10.10.1`, Unbound) devient injoignable car routé via un
> chemin cassé. Symptôme : plus de résolution DNS, navigateur qui
> ne charge plus rien.
>
> La rotation des clés se valide par `ping 10.99.10.1` (hub) — c'est
> suffisant. La validation fonctionnelle complète du tunnel se fait
> depuis un réseau **externe** (4G), et seulement quand OPNsense
> relaie correctement.
>
> Workaround si besoin d'activer le tunnel pendant qu'OPNsense est
> down (DNS coupé) :
> ```bash
> nmcli connection modify homelab ipv4.dns ""
> nmcli connection modify homelab ipv4.ignore-auto-dns yes
> ```

**Test** :

```bash
sudo wg show
# Attendu : interface homelab, peer (VPS), latest handshake récent (qq s)

ping -c 3 10.99.10.1
# Attendu : 3 réponses, ~10-30 ms (latence Hetzner)
```

Si ping KO → STOP, voir § « Rollback » plus bas.

#### 12. Activation du tunnel phone + test (différable)

Sur le phone, si disponible à l'instant T :

1. App WireGuard iOS → supprimer l'ancien tunnel `homelab`.
2. Afficher le QR de la nouvelle conf depuis le laptop :
```bash
   qrencode -t ANSIUTF8 -r ~/homelab/keys/wg-admin-relay/profiles/phone.conf
```
   Ou ouvrir le PNG :
```bash
   xdg-open ~/homelab/keys/wg-admin-relay/profiles/phone.png
```
3. App WireGuard → `+` → « Créer à partir d'un QR code » → scanner.
4. Activer le tunnel.
5. Tester : app Network Ping Lite → ping `10.99.10.1`.

> **Sécurité** : effacer le QR de l'historique terminal après
> import (`clear; history -c` si shell partagé). Le QR contient
> la **privkey** du phone.

Si phone non disponible à l'instant T : le `.conf` et `.png`
restent sur le laptop, reconfigurer dès que possible. Le hub a
déjà la nouvelle pubkey, le phone restera offline en attendant.
Pas d'impact opérationnel tant que l'admin laptop fonctionne.

#### 12b. Reconfiguration OPNsense (différable)

Une fois la clé du peer `opnsense` rotée côté hub et vault, le
tunnel OPNsense reste **down** tant que l'instance WG_ADMIN n'est
pas reconfigurée côté UI OPNsense :

- nouvelle privkey peer (depuis `~/homelab/keys/wg-admin-relay/opnsense.key`),
- nouvelle pubkey hub (depuis `scripts/wg-admin-profiles.yml`).

État acceptable si OPNsense n'a pas besoin du tunnel admin dans
l'immédiat (le hub a déjà la nouvelle pubkey peer, OPNsense
reconnectera dès reconfig). À terme, cette reconfig sera
automatisée via le futur déploiement-as-code OPNsense (cf.
ADR-001) — la reconfig manuelle UI n'est qu'une étape transitoire.

#### 13. Création de l'archive `.tar.gz.age`

```bash
# Récupérer la pubkey age (recipient pour le chiffrement)
AGE_RECIPIENT=$(age-keygen -y ~/.age/homelab.key)
echo "Recipient age : $AGE_RECIPIENT"

cd ~/homelab/keys
```

> **⚠️ Purge obligatoire avant archivage** — l'archive ne doit
> contenir QUE des secrets actuellement en service. Avant le `tar`,
> purger `~/homelab/keys/wg-admin-relay/` de tout secret mort :
>
> - `shred -u` les anciennes clés `*.key.old` (et les supprimer),
> - supprimer tout dossier `archive/` contenant d'anciennes
>   privkeys — anti-pattern : **une clé rotée se détruit, ne
>   s'archive pas**,
> - supprimer les profils (`*.conf`, `*.png`) de peers retirés.
>
> Garder des privkeys mortes dans le backup augmente la surface
> d'exposition sans aucun bénéfice (cf. `docs/secrets-inventory.md`
> sur le risque rétrospectif).
>
> Les `*.old` issus de l'étape 3 sont conservés *côté `~/homelab/keys/wg-admin-relay/`*
> jusqu'au § Nettoyage final (rollback possible), mais **ne doivent
> pas entrer dans l'archive**. Soit on les sort du dossier avant le
> `tar`, soit on les exclut explicitement (`tar --exclude='*.old'`).

```bash
# Création de l'archive chiffrée (avec exclusion des .old)
tar --exclude='*.old' -czf - wg-admin-relay/ | \
  age -r "$AGE_RECIPIENT" > ~/homelab/keys/wg-admin-relay.tar.gz.age
ls -la ~/homelab/keys/wg-admin-relay.tar.gz.age
```

#### 14. Upload sur cloud chiffré privé + test récupération

Selon la méthode actuelle (Google Drive d'après doctrine
existante) ou l'alternative choisie : déposer
`~/homelab/keys/wg-admin-relay.tar.gz.age` à l'endroit prévu.

Tester la récupération AVANT de fermer la session :

```bash
# Simuler une récup
cp ~/homelab/keys/wg-admin-relay.tar.gz.age /tmp/test-recovery.tar.gz.age

# Vérifier qu'on peut bien déchiffrer
age -d -i ~/.age/homelab.key /tmp/test-recovery.tar.gz.age | tar tzf -
# Doit lister :
#   wg-admin-relay/
#   wg-admin-relay/laptop.key
#   wg-admin-relay/laptop.pub
#   wg-admin-relay/phone.key
#   wg-admin-relay/phone.pub
#   wg-admin-relay/profiles/laptop.conf
#   wg-admin-relay/profiles/phone.conf
#   ...

rm /tmp/test-recovery.tar.gz.age
```

#### 15. Commit des changements repo

```bash
cd ~/homelab
git status
```

Attendu — modifications sur :
- `ansible/inventory/group_vars/vps/vault.yml` (diff opaque)
- `scripts/wg-admin-profiles.yml` (pubkey hub)
- `docs/wg-admin-profiles.md` (table OPNsense peer pubkey)
- `docs/operations/key-rotation.md` (entrée journal de rotation
  à ajouter, cf. § « Journal des rotations exécutées » plus bas)

Ajouter l'entrée au journal puis :

```bash
git add ansible/inventory/group_vars/vps/vault.yml \
        scripts/wg-admin-profiles.yml \
        docs/wg-admin-profiles.md \
        docs/operations/key-rotation.md

git commit -m "feat(wg): full rotate WG admin keys (hub + all peers)

Rotation complète des clés WireGuard du tunnel admin :
- Nouvelles privkeys peers générées côté laptop, stockées en
  ~/homelab/keys/wg-admin-relay/.
- Pubkeys peers correspondantes mises à jour dans le vault VPS.
- Privkey hub régénérée côté VPS (suppression forcée puis run du
  rôle wg_admin_hub).
- Pubkey hub mise à jour dans scripts/wg-admin-profiles.yml et
  dans docs/wg-admin-profiles.md (table OPNsense peer).
- Confs clients régénérées via scripts/wg-admin-gen-profile.py.
- Archive ~/homelab/keys/wg-admin-relay.tar.gz.age mise à jour sur cloud
  chiffré privé.

Tunnels laptop et phone validés (handshake récent côté VPS, ping
10.99.10.1 OK depuis chaque peer).

Procédure suivie : docs/operations/key-rotation.md § \"Rotation
full des clés WireGuard admin\"."
```

#### 16. Nettoyage final

```bash
# Suppression sécurisée du backup vault déchiffré
shred -u "$BACKUP_DIR/vault-decrypted-backup.yml"

# Suppression des anciennes clés peers .old côté laptop
rm -f ~/homelab/keys/wg-admin-relay/*.old

# Suppression du fichier pub.old côté VPS
ssh -p 2203 deploy@<ip-vps> 'sudo rm /etc/wireguard/wg-admin.pub.old'

# Le BACKUP_DIR peut être conservé encore quelques jours (par
# précaution), puis supprimé. Ses contenus sensibles ont déjà
# été shreddés.
```

### Rollback

Symptôme déclenchant le rollback : après l'étape 11 ou 12, ping
`10.99.10.1` KO depuis un peer. Diagnostic préalable : vérifier
côté VPS que le service est up et que les peers sont déclarés
(`sudo wg show wg-admin`).

> **⚠️ Point d'attention critique** : **la privkey hub n'est pas
> restaurable après suppression** (pas backupée volontairement,
> doctrine ADR-000 : la privkey ne quitte JAMAIS le VPS). Donc le
> rollback de l'étape 5 (suppression de la privkey hub) n'est pas
> rollbackable. Le seul recours à ce stade est de **terminer le
> cycle complet avec les bonnes valeurs** plutôt que de revenir
> en arrière.
>
> Conséquence pratique : si la rotation est validée jusqu'à
> l'étape 5 incluse, mais foire après, on ne « revient pas à
> l'état avant rotation ». On corrige et on continue jusqu'au
> bout.

#### Rollback étape 11 (laptop foiré) — sans cassure côté VPS

Restaurer l'ancienne conf NetworkManager :

```bash
# Si l'ancienne conf était dans BACKUP_DIR
sudo nmcli connection delete homelab
nmcli connection import type wireguard \
  file "$BACKUP_DIR/laptop.conf"
nmcli connection modify wireguard-laptop connection.id homelab
nmcli connection up homelab
```

⚠️ Ne fonctionnera **pas** : la pubkey hub a changé, l'ancienne
conf laptop a l'ancienne pubkey hub, donc le handshake échouera.
Le rollback réel est de **corriger la nouvelle conf** plutôt que
de restaurer l'ancienne. Diagnostiquer pourquoi la nouvelle conf
laptop ne marche pas (typiquement : mauvaise privkey dans le
fichier, ou mauvaise pubkey hub).

#### Si tout est cassé et que SSH direct reste OK

SSH direct sur 2203 est la voie de récupération canonique. À ce
stade, on garde la main sur le VPS, on peut diagnostiquer et
re-rejouer le rôle Ansible jusqu'à ce que ça marche.

#### Si SSH direct est aussi cassé

Console KVM Hetzner — voie de dernier recours. Réinitialiser
manuellement la conf sshd ou le firewall si nécessaire. Cf.
runbook session-1 § « Rollback manuel via console Hetzner ».

### Journal des rotations exécutées

| Date | Opérateur | Peers rotés | Pubkey hub avant → après | Notes |
|---|---|---|---|---|
| 2026-05-21 | ldesfontaine | laptop, phone, opnsense | 87VrPX34… → 5fOgdc2… | Première rotation full documentée. Peer opnsense roté côté hub + vault, reconfig UI OPNsense différée (déploiement-as-code à venir). Tunnel laptop validé par handshake ; phone profil régénéré ; archive wg-admin-relay.tar.gz.age régénérée et purgée des secrets morts. |
