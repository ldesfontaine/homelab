# WG-ADMIN-RELAY — profils clients

Doctrine, mapping canonique et procédure de génération des profils WireGuard
pour les peers admin externes du homelab.

## Doctrine

Le tunnel **WG-ADMIN-RELAY** permet d'administrer le homelab depuis l'extérieur
(4G, WiFi public, hôtel) sans ouvrir aucun port sur la LiveBox.

**Architecture** :
- Hub : VPS Hetzner — `wg-hub.ldesfontaine.com:51821`
- Peers app : laptop, phone, tablet (générés via le script)
- Peer maison : OPNsense (instance UI, voir plus bas)

Toutes les connexions sont **sortantes** depuis la maison vers le VPS.
LiveBox 100% fermée (aucun port forward, aucun DMZ).

## Mapping canonique

| Peer    | Tunnel IP        | Device(s)                                       |
|---------|------------------|-------------------------------------------------|
| laptop  | `10.99.10.10/32` | ParrotOS — NetworkManager `homelab`             |
| phone   | `10.99.10.11/32` | iPhone — WireGuard iOS app                      |
| tablet  | `10.99.10.12/32` | Tablette (à provisionner)                       |

Tous les peers app utilisent le MÊME `AllowedIPs` canonique :

```
10.99.10.0/24, 10.10.10.0/24, 10.10.60.0/24, 10.10.70.0/24, 10.10.99.0/24
```

| Subnet            | Rôle                                                          |
|-------------------|---------------------------------------------------------------|
| `10.99.10.0/24`   | Subnet WG admin (peers entre eux)                              |
| `10.10.10.0/24`   | MGMT — OPNsense (10.10.10.1), Proxmox UI (10.10.10.20)        |
| `10.10.60.0/24`   | SVC_PRIV — Authentik, Vaultwarden, Filebrowser, Traefik interne |
| `10.10.70.0/24`   | LAB                                                            |
| `10.10.99.0/24`   | BACKUP — Pi5 PBS (futur)                                       |

**Non inclus volontairement** :
- `10.10.20.0/24` (LAN) — pas d'admin externe sur le LAN client
- `10.10.30.0/24` (IOT) — idem
- `10.10.50.0/24` (EXPOSED) — services publics via Pangolin/OIDC, pas via admin
- `0.0.0.0/0` — pas de full-tunnel (variant PARANO en projet, voir limites)

## Procédure d'utilisation

### Lister les peers déclarés

```bash
cd ~/Documents/homelab
python3 scripts/wg-admin-gen-profile.py --list
```

### Générer un profil pour un peer

```bash
python3 scripts/wg-admin-gen-profile.py phone
```

Output : `~/homelab-keys/wg-admin-relay/profiles/phone.conf` + `phone.png` (QR).

### Générer pour tous les peers

```bash
python3 scripts/wg-admin-gen-profile.py --all
```

### Installer sur iOS (phone, tablet)

1. Sur ton laptop : afficher le QR code généré
   ```bash
   xdg-open ~/homelab-keys/wg-admin-relay/profiles/phone.png
   ```
   Ou directement en console :
   ```bash
   qrencode -t ANSIUTF8 -r ~/homelab-keys/wg-admin-relay/profiles/phone.conf
   ```
2. Sur l'iPhone, ouvrir l'app **WireGuard officielle**
3. **+** (en haut à droite) → **Créer à partir d'un QR code**
4. Scanner
5. Nommer le tunnel (ex: `homelab`)
6. Toggle ON

**Note** : supprimer l'ancien profil avant d'importer le nouveau pour éviter
les doublons avec des AllowedIPs divergents.

### Installer sur le laptop (NetworkManager)

```bash
nmcli connection import type wireguard \
  file ~/homelab-keys/wg-admin-relay/profiles/laptop.conf

# Renommer la connexion en "homelab" (convention projet)
nmcli connection modify wireguard-laptop connection.id homelab

# Activer
nmcli connection up homelab
```

Si une connexion `homelab` existe déjà : la supprimer d'abord avec
`nmcli connection delete homelab`.

### Modifier le mapping (ajouter un subnet, un peer)

1. Éditer `scripts/wg-admin-profiles.yml`
2. Regénérer tous les profils :
   ```bash
   python3 scripts/wg-admin-gen-profile.py --all
   ```
3. Réimporter / re-scanner sur chaque device
4. Commit le diff YAML

## Configuration côté OPNsense (peer maison)

⚠️ La config OPNsense n'est PAS gérée par ce script (UI, pas .conf).
Valeurs à saisir manuellement dans `VPN → WireGuard` :

### Instance WG_ADMIN

| Champ                | Valeur                                                |
|----------------------|-------------------------------------------------------|
| Activé               | ☑                                                     |
| Nom                  | `WG_ADMIN`                                            |
| Clé publique         | `gn2LoxjdUXtL0CVNFmNJ5nejGSZXdWhTWM5APr0eVVc=`        |
| Clé privée           | Saisie depuis `~/homelab-keys/wg-admin-relay/opnsense.key` |
| Port d'écoute        | (vide — OPNsense est client, pas serveur)             |
| Adresse du tunnel    | `10.99.10.2/24`                                       |
| Pairs                | `VPS-hub-pangolin`                                    |
| Désactiver les routes | ☐                                                     |

### Peer VPS-hub-pangolin

| Champ                  | Valeur                                                |
|------------------------|-------------------------------------------------------|
| Activé                 | ☑                                                     |
| Nom                    | `VPS-hub-pangolin`                                    |
| Clé publique           | `87VrPX34/AJ22jYmRL9WdrQXZBhEKEgaMO/qfELmyiM=`        |
| Clé pré-partagée       | (vide — non utilisée tant que Phase 9c)              |
| IPs autorisées         | `10.99.10.0/24`                                       |
| Adresse du point final | `wg-hub.ldesfontaine.com`                             |
| Port d'extrémité       | `51821`                                               |
| Intervalle de maintien | `25`                                                  |
| Instances              | `WG_ADMIN`                                            |

## Sécurité

- Les clés privées vivent UNIQUEMENT dans `~/homelab-keys/wg-admin-relay/`
  (chmod 600) — jamais dans le repo
- Archive offsite chiffrée : `~/homelab-keys/wg-admin-relay.tar.gz.age`
  (Google Drive). Clé age maître : `~/.age/homelab.key` (backup Dashlane)
- Les profils générés (`.conf` et `.png`) sont aussi chmod 600 — contiennent
  la clé privée du peer
- Le PNG QR code ne doit JAMAIS être partagé ou laissé visible : il encode
  la clé privée

## Limitations connues

- **Pas de variant PARANO** (full-tunnel via VPS) — Phase 9c future
- **Pas de Pre-Shared Key** (PSK) entre OPNsense et VPS — implique modif
  du template `wg_admin_hub` côté VPS, voir TODO Phase 9c
- **Peer OPNsense géré manuellement via UI** — pas de provider Ansible
  mature au moment de la création du script. À réévaluer périodiquement.

## Références

- Cahier des charges section 11 — tunnels
- ADR-002 — firewall policy
- Runbook session 7 — Phase 9b activation WG-ADMIN-RELAY
- Phases 4 (préparation côté maison) et 9 (hub VPS)
