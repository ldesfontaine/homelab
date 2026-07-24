# 05 — Valider le socle réseau

**État : prêt à exécuter, non exécuté**

## Objectif

Prouver le fonctionnement attendu, les blocages et la reprise après
redémarrage. « J’ai Internet » ne suffit pas à valider le socle.

Noter la date, la machine source, le test et le résultat dans la table de fin.

## 1. Adressage et services communs

| Source | Test | Résultat attendu |
|---|---|---|
| PC admin P2 | renouveler DHCP | `10.10.20.110/24`, gateway/DNS `10.10.20.1` |
| PC USERS P3 | renouveler DHCP | adresse `10.10.20.100-199`, sauf `.110` |
| PC LAB P4 | renouveler DHCP | adresse `10.10.40.100-199`, gateway/DNS `10.10.40.1` |
| chaque PC | résolution d’un domaine normal | autorisée |
| chaque PC | accès web Internet | autorisé |
| chaque PC | synchronisation de l’heure | autorisée, OPNsense local ou upstream du poste |

## 2. Prouver la chaîne Quad9

Depuis un poste disposant de `dig` :

```sh
dig +short txt proto.on.quad9.net.
dig brokendnssec.net A
dig @1.1.1 example.com A
```

Résultats attendus :

1. `proto.on.quad9.net` retourne `"dot"` ;
2. `brokendnssec.net` échoue avec `SERVFAIL` ;
3. la requête directe vers `1.1.1:53` est refusée ou expire.

Depuis Windows sans `dig`, utiliser
`Resolve-DnsName -Type TXT proto.on.quad9.net.` pour le premier test. Le site
`https://on.quad9.net` doit également confirmer Quad9.

Dans la capture WAN OPNsense, filtrer `port 53 or port 853` pendant une nouvelle
résolution : les échanges du firewall vers l’amont doivent être en TCP 853,
sans requête DNS sortante en clair.

Tester aussi une connexion directe vers `1.1.1:853` : elle doit être bloquée
depuis les clients. Un navigateur configuré en DoH ou un VPN peut contourner
ce contrôle sur TCP 443 ; cette limite doit être notée, pas masquée.

## 3. Prouver les isolations

| Source | Destination | Résultat attendu |
|---|---|---|
| PC admin `10.10.20.110` | WebGUI OPNsense TCP 443 | autorisé |
| autre PC USERS | WebGUI OPNsense | refusé |
| PC admin | switch `10.10.20.2` | autorisé |
| autre PC USERS | switch `10.10.20.2` | refusé par le contrôle d’accès du switch |
| PC LAB | PC USERS | refusé |
| PC LAB | switch `10.10.20.2` | refusé |
| PC LAB | adresse OPNsense sur USERS ou RESCUE | refusé |
| PC LAB | interface Livebox | refusé |
| Internet | WebGUI ou SSH OPNsense | refusé |

Observer dans `Firewall > Log Files > Live View` au moins un blocage
`LAB_PC -> HOME_NETS`. L’absence de réponse seule n’est pas une preuve si le
log ne montre pas la règle attendue.

## 4. Prouver la récupération

1. exporter les configurations OPNsense et switch ;
2. débrancher temporairement WAN ;
3. relier un PC statique `10.10.254.2/24` directement à `RESCUE` ;
4. vérifier `https://10.10.254.1` ;
5. rebrancher WAN et confirmer la reconnexion ;
6. redémarrer OPNsense, puis valider DHCP, DNS, règles et `RESCUE` ;
7. redémarrer le switch, puis valider les VLAN et son contrôle d’accès ;
8. comparer les exports finaux aux checkpoints attendus.

Ne pas redémarrer OPNsense et le switch simultanément : cela rendrait la cause
d’une panne ambiguë.

## 5. Sauvegardes

Les exports peuvent contenir comptes, topologie, empreintes ou secrets :

- aucune copie en clair dans Git ;
- chiffrement `age` avant ajout sous `backups/` ;
- clé privée conservée hors du dépôt ;
- seconde copie chiffrée hors Git ;
- test de déchiffrement dans un dossier temporaire hors dépôt ;
- restauration complète privilégiée pour OPNsense, les restaurations partielles
  pouvant laisser une configuration incohérente.

Le test de restauration réel peut être différé s’il nécessite d’interrompre le
réseau, mais il doit rester visible comme non validé.

## Résultats

| Date | Source | Test | Résultat | Observation |
|---|---|---|---|---|
| — | — | Non exécuté | — | — |

## Critère de clôture

La partie 1 passe de **Configuré** à **Validé** uniquement si :

- chaque test attendu et interdit est conforme ;
- les résultats restent conformes après les deux redémarrages ;
- le port `RESCUE` fonctionne ;
- P5 est libre ;
- les deux configurations finales existent sous forme chiffrée ;
- toute exception est documentée au lieu d’être assimilée à une réussite.

Après cette clôture seulement, une petite blocklist DNS pour `USERS` pourra
être testée, puis la partie 2 Proxmox pourra commencer.
