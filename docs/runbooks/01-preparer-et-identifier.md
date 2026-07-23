# 01 — Préparer et identifier

**État : brouillon, non exécuté**

## Objectif

Préparer le matériel sans couper l’accès Internet existant et identifier les
ports du CWWK avant de leur attribuer un rôle.

## Prérequis

- un PC avec port Ethernet ;
- un câble Ethernet connu comme fonctionnel ;
- écran et clavier pour le CWWK si nécessaire ;
- accès administrateur à la Livebox ;
- support d’installation OPNsense si le système n’est pas déjà présent ;
- moyen de noter les correspondances privées hors du dépôt.

## Contrôles avant action

1. confirmer que le Wi-Fi Livebox fournit toujours Internet ;
2. relever l’adresse LAN de la Livebox sans la publier ;
3. vérifier si OPNsense est installé et connaître sa version ;
4. ne brancher aucun câble Livebox sur le switch interne ;
5. photographier ou dessiner l’ordre physique des six prises CWWK.

## Identification des ports

Pour chaque prise :

1. brancher un seul câble ;
2. observer l’interface dont l’état passe à `up` dans OPNsense ;
3. noter la correspondance localement ;
4. débrancher et recommencer avec la prise suivante ;
5. poser une étiquette de rôle seulement après vérification.

Les rôles finaux sont `WAN`, `TRUNK-SWITCH`, `TRUNK-PROXMOX`, `BACKUP`,
`RESCUE` et `SPARE`.

## Validation

- les six prises ont une correspondance non ambiguë ;
- aucune information privée n’a été ajoutée au dépôt ;
- la Livebox continue à fournir le moyen de retour arrière.

## Retour arrière

Débrancher le CWWK et remettre le PC sur la Livebox. Cette étape ne doit encore
avoir modifié ni le switch ni la configuration réseau des PC.
