# 04 — Configurer le switch et les VLAN

**État : prêt à exécuter, non exécuté**

## Résultat attendu

P1 transporte uniquement les VLAN taggés 20 et 40 vers OPNsense. P2 et P3
servent `USERS`, P4 sert `LAB-PC`, P5 reste inutilisé. L’interface du switch
n’est joignable que depuis le poste d’administration.

## Limite connue du MS305E

Le manuel officiel ne documente pas de VLAN de management dédié. Le switch
reçoit donc `10.10.20.2/24` et son interface est protégée par :

- un mot de passe unique ;
- la liste d’accès IP du switch limitée à `10.10.20.110` ;
- aucune publication ni redirection ;
- un accès local au même réseau de niveau 2.

Cette protection est correcte pour la contrainte matérielle, mais n’équivaut
pas à un plan de management séparé.

## 1. Préparer le retour arrière

1. laisser P1 débranché d’OPNsense ;
2. relier uniquement le poste d’administration à P2 ;
3. si aucun DHCP n’est présent, mettre le PC en `192.168.0.210/24` ;
4. ouvrir l’adresse actuelle du switch ; après reset, son fallback est
   `192.168.0.239` et son mot de passe est `password` ;
5. changer immédiatement le mot de passe ;
6. relever la version du firmware ;
7. exporter la configuration depuis `SETTINGS > BACKUP > BACKUP`.

Conserver la première sauvegarde hors Git. Si une mise à jour firmware officielle
est nécessaire, la faire maintenant par câble et ne jamais couper le réseau ou
l’alimentation pendant l’écriture et le redémarrage.

## 2. Fixer l’adresse d’administration

Dans les paramètres IP du switch :

- DHCP : désactivé ;
- adresse : `10.10.20.2` ;
- masque : `255.255.255.0` ;
- gateway : `10.10.20.1`.

Après application, mettre temporairement le PC en `10.10.20.110/24` et rouvrir
`10.10.20.2`.

Dans `SETTINGS > ACCESS CONTROL` :

1. ajouter `10.10.20.110` à la liste autorisée ;
2. vérifier que l’entrée est enregistrée ;
3. activer le contrôle d’accès ;
4. ouvrir une nouvelle session avant de fermer l’ancienne.

Ne jamais activer la liste vide : selon le manuel, une liste sans adresse ne
restreint pas les sources comme attendu.

Exporter un nouveau checkpoint avant les VLAN.

## 3. Configurer Advanced 802.1Q

Activer **Advanced 802.1Q VLAN**. Créer les VLAN 20, 40 et 4094, puis appliquer
la matrice suivante :

| VLAN | P1 | P2 | P3 | P4 | P5 |
|---:|---|---|---|---|---|
| 1 | Excluded | Excluded | Excluded | Excluded | Untagged |
| 20 | Tagged | Untagged | Untagged | Excluded | Excluded |
| 40 | Tagged | Excluded | Excluded | Untagged | Excluded |
| 4094 | Untagged | Excluded | Excluded | Excluded | Excluded |

Puis définir les PVID :

| Port | PVID |
|---:|---:|
| P1 | 4094 |
| P2 | 20 |
| P3 | 20 |
| P4 | 40 |
| P5 | 1 |

P1 n’a donc aucun réseau utile non taggé. OPNsense ne crée pas d’interface
VLAN 4094 : tout trafic natif accidentel termine dans une impasse.

Désactiver administrativement P5 si le firmware le permet ; sinon le laisser
physiquement vide. Les VLAN 10 et 30 ne sont pas encore ajoutés.

Effectuer les changements depuis P2 et appliquer le PVID de P2 en dernier. Une
coupure de la session pendant la modification est possible ; remettre le PC en
`10.10.20.110/24` et rouvrir `10.10.20.2`.

## 4. Brancher et migrer un port à la fois

1. relier P1 au port OPNsense `TRUNK-SWITCH` ;
2. laisser le poste d’administration sur P2 ;
3. remettre sa carte réseau en DHCP ;
4. vérifier la réservation `10.10.20.110`, DNS, Internet et WebGUI OPNsense ;
5. vérifier l’accès à `10.10.20.2` ;
6. brancher le second PC de confiance sur P3 et refaire les tests ;
7. brancher le PC d’expérimentation sur P4 ;
8. vérifier son adresse `10.10.40.x`, Internet et son isolement ;
9. confirmer que P5 reste vide.

Exporter la configuration finale du switch et la chiffrer avant toute copie
dans le dépôt.

## Difficultés probables

| Symptôme | Cause probable | Action |
|---|---|---|
| aucun DHCP sur P2/P3 | P1 non taggé, VLAN 20 absent ou PVID incorrect | contrôler VLAN 20 taggé P1, non taggé accès |
| aucun DHCP sur P4 | VLAN 40 ou PVID 40 incorrect | contrôler les deux extrémités |
| switch joignable avant, plus après VLAN | limite de gestion non taggée ou mauvaise IP | accès direct P2 en `10.10.20.110/24`, puis rollback |
| Internet fonctionne mais pas la WebGUI | source différente de `ADMIN_PC` | contrôler la réservation DHCP et la règle USERS |
| trafic étrange non taggé sur P1 | VLAN natif utile restant | vérifier PVID/untagged 4094 et absence d’interface 4094 |
| débit limité à 1 Gb/s | câble, négociation ou port du PC | vérifier les deux extrémités ; ne pas forcer la vitesse d’abord |

## Retour arrière

Premier niveau : débrancher P1, relier le PC directement à P2 et utiliser
`10.10.20.110/24` pour restaurer le checkpoint `.cfg`.

Dernier recours : maintenir le bouton RESET plus de cinq secondes. Attendre le
redémarrage complet, environ une minute, sans couper alimentation ni câbles.
Cette action efface toute la configuration ; le switch revient en DHCP avec
fallback `192.168.0.239` et mot de passe `password`.
