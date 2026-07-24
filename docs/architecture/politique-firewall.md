# Politique du firewall

## Principe

Une communication est bloquée tant qu’elle n’est pas explicitement nécessaire.
Les règles sont appliquées sur le réseau d’où part la connexion.

Les besoins communs comme le DNS et la synchronisation de l’heure doivent
utiliser OPNsense ou une destination explicitement approuvée.

Les règles sont placées sur l’interface où la connexion commence. OPNsense les
traite dans l’ordre, avec la première correspondance gagnante pour les règles
rapides par défaut. L’ordre écrit dans les tableaux est donc une partie de la
politique.

## Politique cible

| Origine | Internet | MGMT | USERS | LAB | SERVICES-PRIVATE | EDGE |
|---|---:|---:|---:|---:|---:|---:|
| `MGMT` | Oui | Borné | Administration | Administration | Administration | Administration |
| `USERS` | Oui | Non, sauf poste admin | Même réseau | Accès choisi | Ports publiés | Non |
| `LAB` | Oui | Non | Non | Oui par routage | Non par défaut | Non |
| `SERVICES-PRIVATE` | Besoin explicite | Non | Non initié | Non | Selon service | Non |
| `EDGE` | Besoin explicite | Non | Non | Non | Backends précis | Selon composant |

`Borné` signifie que l’accès est limité aux équipements, sources et ports
nécessaires ; il ne s’agit pas d’un `allow any`.

## Alias de la partie 1

| Alias | Contenu |
|---|---|
| `ADMIN_PC` | `10.10.20.110` |
| `HOME_NETS` | `10.10.0.0/16` et réseau LAN réel de la Livebox |
| `DNS_PORTS` | TCP/UDP 53 |
| `DOT_PORT` | TCP 853 |

Le réseau Livebox reste une valeur privée relevée localement. L’alias l’inclut
afin que `LAB-PC` ne puisse pas administrer la box en contournant les VLAN.

## Règles `USERS`, dans cet ordre

| Action | Source | Destination | Port | Rôle |
|---|---|---|---|---|
| Pass | `USERS net` | `USERS address` | `DNS_PORTS` | DNS local |
| Pass | `USERS net` | `USERS address` | UDP 123 | heure locale |
| Pass | `ADMIN_PC` | `This Firewall` | TCP 443 | administration |
| Reject + log | `USERS net` | `This Firewall` | tous | protéger le firewall |
| Reject + log | `USERS net` | `HOME_NETS` | tous | aucune autre zone pour l’instant |
| Reject + log | `USERS net` | tous | `DNS_PORTS`, puis `DOT_PORT` | empêcher le DNS direct |
| Pass | `USERS net` | tous | tous | Internet |

Le switch est atteint directement au niveau 2 sur `10.10.20.2` : ce trafic ne
traverse pas OPNsense et dépend du contrôle d’accès propre au MS305E.

## Règles `LAB-PC`, dans cet ordre

| Action | Source | Destination | Port | Rôle |
|---|---|---|---|---|
| Pass | `LAB-PC net` | `LAB-PC address` | `DNS_PORTS` | DNS local |
| Pass | `LAB-PC net` | `LAB-PC address` | UDP 123 | heure locale |
| Reject + log | `LAB-PC net` | `This Firewall` | tous | aucune administration |
| Reject + log | `LAB-PC net` | `HOME_NETS` | tous | isoler le LAB |
| Reject + log | `LAB-PC net` | tous | `DNS_PORTS`, puis `DOT_PORT` | empêcher le DNS direct |
| Pass | `LAB-PC net` | tous | tous | Internet |

Il n’y a aucune règle entrante sur WAN et aucune redirection Livebox vers
OPNsense. Le refus implicite reste actif pour tout ce qui n’est pas listé.

IPv6 est désactivé globalement pendant la partie 1 ; il ne peut pas devenir un
chemin non filtré parallèle.

## Partie 2

`LAB-PC` et `LAB-VM` seront regroupés dans la zone `LAB`. Une règle permettra
leur communication IP si les expérimentations l’exigent, sans ouvrir l’accès
vers `USERS` ou `MGMT`.

## Publication future

Un service privé reste dans `SERVICES-PRIVATE`, même lorsqu’un utilisateur
distant y accède au travers d’un tunnel. Le connecteur ou frontal exposé est
placé dans `EDGE` et ne reçoit qu’une autorisation précise vers le backend.
