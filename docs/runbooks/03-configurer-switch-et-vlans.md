# 03 — Configurer le switch et les VLAN

**État : brouillon, non exécuté**

## Objectif

Créer `USERS` et `LAB-PC`, raccorder les trois PC et conserver P5 pour la future
borne.

## Préparation OPNsense

Sur l’interface physique `TRUNK-SWITCH`, créer :

- VLAN 10 `MGMT-NET` — réservé si nécessaire pour la gestion côté switch ;
- VLAN 20 `USERS` ;
- VLAN 30 `IOT` — réservé, sans DHCP ni règle d’accès pendant la partie 1 ;
- VLAN 40 `LAB-PC`.

Activer DHCP uniquement sur les réseaux réellement utilisés. Les plages exactes
seront choisies pendant l’exécution.

## Configuration MS305E

Utiliser le mode **Advanced 802.1Q VLAN**.

| VLAN | P1 | P2 | P3 | P4 | P5 |
|---:|---|---|---|---|---|
| 10 | Tagged | Excluded | Excluded | Excluded | Untagged |
| 20 | Tagged | Untagged | Untagged | Excluded | Tagged |
| 30 | Tagged | Excluded | Excluded | Excluded | Tagged |
| 40 | Tagged | Excluded | Excluded | Untagged | Excluded |

PVID :

- P2 → 20 ;
- P3 → 20 ;
- P4 → 40 ;
- P5 → 10, uniquement lors de l’installation future de la borne.

P1 ne doit transporter aucun trafic non taggé utile. Le comportement du switch
pour son propre accès d’administration doit être vérifié avant de retirer son
accès direct.

## Ordre de migration

1. configurer les VLAN sur OPNsense ;
2. configurer le switch depuis un PC directement raccordé ;
3. raccorder P1 à `TRUNK-SWITCH` ;
4. migrer un seul PC de confiance sur P2 ;
5. valider DHCP, DNS et Internet ;
6. migrer le second PC sur P3 ;
7. migrer le PC de LAB sur P4 ;
8. laisser P5 libre.

## Validation

La validation complète est décrite dans
[`04-valider-le-socle-reseau.md`](04-valider-le-socle-reseau.md).

## Retour arrière

Conserver une copie de la configuration initiale du switch. En cas d’échec,
débrancher P1, remettre le switch dans son état précédent et reconnecter les PC
à la Livebox selon le câblage de secours préparé.
