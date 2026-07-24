# Zones et VLAN

Les adresses sont réservées pour garder un plan lisible. Avant exécution, il
faut confirmer que `10.10.0.0/16` n’entre pas en conflit avec un VPN réellement
utilisé.

## Réseaux transportés par le switch

| VLAN | Nom | Sous-réseau prévu | Usage | État partie 1 |
|---:|---|---|---|---|
| 10 | `MGMT-NET` | `10.10.10.0/24` | future borne et futurs équipements administrés | Réservé |
| 20 | `USERS` | `10.10.20.0/24` | deux PC de confiance, futur Wi-Fi principal | À configurer |
| 30 | `IOT` | `10.10.30.0/24` | futur Wi-Fi IoT | Réservé |
| 40 | `LAB-PC` | `10.10.40.0/24` | PC d’expérimentation | À configurer |

La partie 1 ne crée réellement que les VLAN 20 et 40. Les autres numéros sont
réservés dans le plan, mais ne sont pas transportés sur le trunk tant qu’ils ne
servent pas.

Le MS305E lui-même utilise `10.10.20.2/24`. Cette adresse n’indique pas qu’il
appartient techniquement à un VLAN de management : ce modèle n’en documente
pas. Son interface reste joignable localement dans `USERS` et son contrôle
d’accès autorise uniquement le poste d’administration.

## Réseaux transportés vers Proxmox

| VLAN | Nom | Sous-réseau prévu | Usage | Partie |
|---:|---|---|---|---|
| 11 | `MGMT-COMPUTE` | `10.10.11.0/24` | hôte Proxmox | 2 |
| 41 | `LAB-VM` | `10.10.41.0/24` | VM d’expérimentation | 2 |
| 50 | `SERVICES-PRIVATE` | `10.10.50.0/24` | applications et données internes | 2+ |
| 60 | `EDGE` | `10.10.60.0/24` | connecteurs et frontaux exposés | Réservé |

Les VLAN 10 et 11 formeront plus tard la zone de sécurité `MGMT`. Les VLAN 40
et 41 formeront la zone `LAB`. Ils gardent des sous-réseaux distincts parce
qu’ils arrivent sur deux ports physiques différents d’OPNsense.

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

## Adresse réservée au poste d’administration

Le poste autorisé à administrer OPNsense et le switch reçoit
`10.10.20.110/24` par réservation DHCP. Sa MAC reste une donnée locale non
versionnée.

Cette adresse appartient volontairement à la plage Dnsmasq. La réservation doit
être créée avant d’activer le pool dynamique afin qu’elle ne soit jamais
attribuée à un autre poste.
