# Câblage

## CWWK / OPNsense

Les noms ci-dessous décrivent des rôles. Ils ne doivent pas être associés à
`igc0`, `igc1`, etc. avant l’identification réelle des six prises.

| Rôle | Liaison | Usage |
|---|---|---|
| `WAN` | Livebox 6 → CWWK | Accès Internet |
| `TRUNK-SWITCH` | CWWK → MS305E P1 | Réseaux filaires et future borne |
| `TRUNK-PROXMOX` | CWWK → Proxmox | Management compute, LAB-VM, services, EDGE |
| `BACKUP` | CWWK → Pi 5 | Réseau de sauvegarde dédié |
| `RESCUE` | CWWK → PC temporaire | Récupération locale d’OPNsense |
| `SPARE` | non branché | Réserve |

`TRUNK-PROXMOX` et `BACKUP` sont réservés pendant la partie 1. Leur présence
dans le plan ne signifie pas qu’ils sont configurés.

## Netgear MS305E

| Port | Équipement | Configuration cible |
|---:|---|---|
| P1 | OPNsense `TRUNK-SWITCH` | VLAN 20 et 40 taggés ; VLAN 4094 natif inutilisé |
| P2 | PC de confiance 1 | VLAN 20 non taggé, PVID 20 |
| P3 | PC de confiance 2 | VLAN 20 non taggé, PVID 20 |
| P4 | PC d’expérimentation | VLAN 40 non taggé, PVID 40 |
| P5 | Future borne Wi-Fi | libre et désactivé pendant la partie 1 |

Le VLAN 4094 est une impasse : OPNsense ne lui attribue aucune interface. Il
absorbe le trafic non taggé accidentel du trunk. Les VLAN 10 et 30 seront
ajoutés à P1 et P5 uniquement lors de l’installation future de la borne.

## Règles de câblage

- étiqueter les deux extrémités de chaque câble ;
- conserver un accès Livebox indépendant pendant la migration ;
- ne jamais supposer l’ordre physique des interfaces CWWK ;
- ne pas relier deux ports OPNsense au même switch sans agrégation ou décision
  explicite ;
- garder le port `RESCUE` disponible avant toute modification de VLAN ;
- noter uniquement les rôles dans le dépôt public, jamais les adresses MAC ou
  numéros de série.
