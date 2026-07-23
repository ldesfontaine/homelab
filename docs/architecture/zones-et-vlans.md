# Zones et VLAN

Les adresses sont réservées pour garder un plan lisible. Elles devront être
vérifiées contre les VPN et réseaux existants avant configuration.

## Réseaux transportés par le switch

| VLAN | Nom | Sous-réseau prévu | Usage | Partie |
|---:|---|---|---|---|
| 10 | `MGMT-NET` | `10.10.10.0/24` | future borne et équipements raccordés au switch | 1 |
| 20 | `USERS` | `10.10.20.0/24` | deux PC de confiance, futur Wi-Fi principal | 1 |
| 30 | `IOT` | `10.10.30.0/24` | futur Wi-Fi IoT | Réservé |
| 40 | `LAB-PC` | `10.10.40.0/24` | PC d’expérimentation | 1 |

## Réseaux transportés vers Proxmox

| VLAN | Nom | Sous-réseau prévu | Usage | Partie |
|---:|---|---|---|---|
| 11 | `MGMT-COMPUTE` | `10.10.11.0/24` | hôte Proxmox | 2 |
| 41 | `LAB-VM` | `10.10.41.0/24` | VM d’expérimentation | 2 |
| 50 | `SERVICES-PRIVATE` | `10.10.50.0/24` | applications et données internes | 2+ |
| 60 | `EDGE` | `10.10.60.0/24` | connecteurs et frontaux exposés | Réservé |

Les VLAN 10 et 11 forment plus tard la zone de sécurité `MGMT`. Les VLAN 40 et
41 forment la zone `LAB`. Ils gardent des sous-réseaux distincts parce qu’ils
arrivent sur deux ports physiques différents d’OPNsense.

## Réseaux physiques dédiés

| Nom | Sous-réseau prévu | Usage |
|---|---|---|
| `BACKUP` | `10.10.90.0/24` | liaison Pi 5 et sauvegardes |
| `RESCUE` | `10.10.254.0/24` | accès direct d’urgence à OPNsense |

Ces liaisons n’ont pas besoin d’un tag VLAN tant qu’elles restent directement
branchées sur un port OPNsense. Le numéro 90 pourra devenir un ID de VLAN si le
réseau de sauvegarde passe un jour par un switch.

## Passerelles

OPNsense utilisera l’adresse `.1` de chaque réseau activé. Aucun sous-réseau ne
doit être activé sur deux interfaces différentes.
