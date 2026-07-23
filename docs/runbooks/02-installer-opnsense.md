# 02 — Installer OPNsense

**État : brouillon, non exécuté**

## Objectif

Obtenir un firewall administrable localement, avec un WAN Livebox et un port de
secours indépendant des VLAN.

## Garde importante

La Livebox utilise couramment `192.168.1.1`. L’interface LAN par défaut
d’OPNsense ne doit pas conserver le même réseau lorsque le WAN est branché à la
Livebox.

## Séquence

1. installer ou réinitialiser OPNsense depuis une image officielle vérifiée ;
2. assigner les rôles `WAN` et `RESCUE` d’après l’identification physique ;
3. configurer `RESCUE` sur `10.10.254.1/24` ;
4. connecter le PC directement au port `RESCUE` ;
5. changer le mot de passe administrateur ;
6. interdire l’administration depuis le WAN ;
7. brancher `WAN` sur le port 2,5 GbE de la Livebox ;
8. obtenir une adresse WAN par DHCP ;
9. vérifier DNS, heure et accès Internet depuis OPNsense ;
10. mettre OPNsense à jour avant de créer les VLAN ;
11. exporter une première configuration et la chiffrer hors du dépôt.

L’interface graphique exacte et les noms de menus seront complétés pendant
l’exécution, en fonction de la version réellement installée.

## Validation

- le PC atteint l’interface OPNsense uniquement par `RESCUE` ;
- OPNsense atteint Internet par la Livebox ;
- aucune règle WAN n’expose l’administration ;
- débrancher `WAN` ne bloque pas l’accès local par `RESCUE` ;
- une sauvegarde chiffrée existe hors du firewall.

## Retour arrière

Débrancher le WAN OPNsense et conserver la Livebox comme accès principal. En
cas de perte d’administration, reconnecter le PC directement à `RESCUE`.
