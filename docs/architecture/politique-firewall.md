# Politique du firewall

## Principe

Une communication est bloquée tant qu’elle n’est pas explicitement nécessaire.
Les règles sont appliquées sur le réseau d’où part la connexion.

Les besoins communs comme le DNS et la synchronisation de l’heure doivent
utiliser OPNsense ou une destination explicitement approuvée.

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

## Partie 1

Seuls `USERS`, `LAB-PC`, `MGMT-NET` si nécessaire et `RESCUE` sont concernés.
Les règles minimales attendues sont :

1. autoriser DNS et NTP vers OPNsense ;
2. autoriser `USERS` vers Internet ;
3. autoriser `LAB-PC` vers Internet ;
4. bloquer `LAB-PC` vers tous les réseaux internes ;
5. autoriser l’administration d’OPNsense depuis une source de confiance ;
6. conserver le refus implicite pour tout le reste.

L’IPv6 ne sera pas laissé actif sans règles équivalentes et validation dédiée.

## Partie 2

`LAB-PC` et `LAB-VM` seront regroupés dans la zone `LAB`. Une règle permettra
leur communication IP si les expérimentations l’exigent, sans ouvrir l’accès
vers `USERS` ou `MGMT`.

## Publication future

Un service privé reste dans `SERVICES-PRIVATE`, même lorsqu’un utilisateur
distant y accède au travers d’un tunnel. Le connecteur ou frontal exposé est
placé dans `EDGE` et ne reçoit qu’une autorisation précise vers le backend.
