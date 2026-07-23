# 04 — Valider le socle réseau

**État : brouillon, non exécuté**

## Objectif

Prouver le fonctionnement attendu et les blocages, pas seulement constater que
les PC ont Internet.

## Matrice minimale

| Source | Test | Résultat attendu |
|---|---|---|
| PC `USERS` | obtenir une adresse DHCP | Autorisé, réseau `10.10.20.0/24` |
| PC `USERS` | résoudre un nom DNS | Autorisé |
| PC `USERS` | atteindre Internet | Autorisé |
| PC `LAB-PC` | obtenir une adresse DHCP | Autorisé, réseau `10.10.40.0/24` |
| PC `LAB-PC` | résoudre un nom DNS | Autorisé |
| PC `LAB-PC` | atteindre Internet | Autorisé |
| PC `LAB-PC` | atteindre un PC `USERS` | Bloqué |
| PC `LAB-PC` | atteindre l’administration OPNsense | Bloqué |
| PC `USERS` non administrateur | atteindre l’administration | Bloqué |
| PC d’administration | atteindre l’administration | Autorisé |
| Internet | atteindre l’administration OPNsense | Bloqué |

Chaque test doit noter la date, la source, la destination et le résultat dans
la section suivante.

## Résultats

À compléter pendant l’exécution.

| Date | Test | Résultat | Observation |
|---|---|---|---|
| — | Non exécuté | — | — |

## Contrôles complémentaires

- vérifier les journaux OPNsense lors d’un blocage LAB → USERS ;
- redémarrer OPNsense puis vérifier le retour des réseaux ;
- redémarrer le switch puis vérifier le retour des VLAN ;
- confirmer que P5 est libre ;
- confirmer que le port `RESCUE` fonctionne toujours ;
- exporter puis chiffrer les configurations OPNsense et switch.

## Critère de clôture

La partie 1 passe de **Configuré** à **Validé** uniquement lorsque toute la
matrice obligatoire est conforme après un redémarrage des équipements.
