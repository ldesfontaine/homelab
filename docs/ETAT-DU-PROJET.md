# État du projet

Dernière mise à jour : 23 juillet 2026.

## Lecture des états

- **Planifié** : décision écrite, aucune configuration réelle ne la prouve.
- **Configuré** : changement appliqué sur le matériel concerné.
- **Validé** : comportement attendu et comportement interdit testés.

## Situation actuelle

Le Homelab est considéré comme indisponible, même si certains éléments
historiques peuvent encore fonctionner. La Livebox fournit toujours la
connexion et le Wi-Fi. OPNsense, le switch, Proxmox et le Pi 5 doivent être
intégrés ou réintégrés depuis une base connue.

| Partie | Périmètre | État |
|---|---|---|
| 1 — Socle réseau | OPNsense, switch, VLAN et règles réseau | Planifié |
| 2 — Proxmox | Hyperviseur et premier service de test | Non commencé |
| 3 — Your Cloud | Observation puis intégration bornée | Non commencé |

## Partie active : socle réseau

La partie 1 doit produire un réseau domestique utilisable sans dépendre de
Proxmox, du VPS, du Pi 5, de Your Cloud ou de la future borne Wi-Fi.

Elle sera terminée lorsque :

- la Livebox fournit Internet à OPNsense ;
- les deux PC de confiance utilisent le réseau `USERS` ;
- le PC d’expérimentation utilise le réseau `LAB-PC` ;
- les réseaux autorisés atteignent Internet ;
- le LAB ne peut pas initier de connexion vers `USERS` ou l’administration ;
- l’administration d’OPNsense reste récupérable par un port physique dédié ;
- les configurations OPNsense et switch sont sauvegardées sous forme chiffrée ;
- les tests attendus et interdits du runbook de validation sont passés.

## Hors périmètre actuel

- configuration de la future borne Wi-Fi ;
- Proxmox et ses machines virtuelles ;
- Pi 5 et sauvegardes Proxmox ;
- publication de services depuis la maison ;
- connexion au VPS ;
- intégration ou contrôle par Your Cloud.

Les réseaux nécessaires à ces usages peuvent être réservés, mais ils ne seront
pas présentés comme configurés avant leur mise en place réelle.

## Prochain point de contrôle

1. vérifier si OPNsense est déjà installé sur le CWWK ;
2. identifier la correspondance entre les six prises physiques et les
   interfaces vues par OPNsense ;
3. étiqueter les câbles et les ports ;
4. conserver un accès Internet Livebox indépendant pendant les essais.
