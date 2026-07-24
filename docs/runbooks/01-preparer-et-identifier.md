# 01 — Préparer et identifier

**État : brouillon, non exécuté**

## Objectif

Préparer le matériel sans couper l’accès Internet existant et identifier les
ports du CWWK avant de leur attribuer un rôle.

## Prérequis

- un PC avec port Ethernet ;
- un câble Ethernet connu comme fonctionnel ;
- écran et clavier pour le CWWK ;
- accès administrateur à la Livebox ;
- une clé USB dédiée à l’installation ;
- moyen de noter les correspondances privées hors du dépôt.

## Contrôles avant action

1. confirmer que le Wi-Fi Livebox fournit toujours Internet ;
2. relever le réseau LAN de la Livebox sans le publier ;
3. confirmer qu’aucun VPN utilisé n’emploie `10.10.0.0/16` ;
4. accepter que le disque choisi dans le CWWK sera entièrement effacé ;
5. ne brancher aucun câble Livebox sur le switch interne ;
6. photographier ou dessiner l’ordre physique des six prises CWWK.

## Identification des ports

L’ordre `igc0`, `igc1`, etc. n’est pas déduit de l’ordre des prises. Les Intel
i226-V sont pris en charge par le pilote `igc`, mais le câblage interne du
constructeur décide de leur numérotation.

Depuis la console OPNsense, pour chaque prise :

1. brancher un seul câble ;
2. observer l’interface dont l’état passe à `up` dans OPNsense ;
3. noter la correspondance localement ;
4. débrancher et recommencer avec la prise suivante ;
5. poser une étiquette de rôle seulement après vérification.

Les rôles finaux sont `WAN`, `TRUNK-SWITCH`, `TRUNK-PROXMOX`, `BACKUP`,
`RESCUE` et `SPARE`.

Au moment de l’installation, seuls `WAN` et `RESCUE` sont assignés. Les autres
rôles sont des étiquettes physiques ; ils seront configurés plus tard.

## Validation

- les six prises ont une correspondance non ambiguë ;
- aucune information privée n’a été ajoutée au dépôt ;
- la Livebox continue à fournir le moyen de retour arrière.

## Retour arrière

Débrancher le CWWK et remettre le PC sur la Livebox. Cette étape ne doit encore
avoir modifié ni le switch ni la configuration réseau des PC.
