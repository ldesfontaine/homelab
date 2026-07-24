# 02 — Installer OPNsense

**État : prêt à exécuter, non exécuté**

## Résultat attendu

OPNsense démarre sur le disque interne du CWWK, reste administrable par un port
physique `RESCUE` et accède à Internet par la Livebox. Aucun VLAN n’est encore
créé.

## Garde importante

La Livebox utilise par défaut `192.168.1.0/24` et `192.168.1.1`. L’interface
LAN par défaut d’OPNsense utilise aussi `192.168.1.1`. Ne jamais connecter
simultanément ces deux interfaces dans cet état.

Le Wi-Fi Livebox reste disponible pendant toute l’installation.

## 1. Préparer une image vérifiée

1. télécharger la dernière image **Community Edition**, architecture
   `amd64`, type **VGA**, depuis le site officiel OPNsense ;
2. télécharger sur la même page le checksum, la signature et la clé publique
   correspondant exactement à cette série ;
3. comparer le SHA-256 de l’archive téléchargée au checksum publié ;
4. décompresser l’image `.bz2` ;
5. vérifier la signature de l’image décompressée avec la clé officielle ;
6. écrire l’image sur la clé USB avec un outil qui affiche explicitement le
   périphérique cible.

Depuis OPNsense 24.1, la signature porte sur l’image décompressée. Une
différence de checksum ou une signature invalide arrête l’installation : on ne
réessaie pas avec le même fichier.

La [procédure officielle d’installation](https://docs.opnsense.org/manual/install.html)
reste la référence pour les noms exacts des fichiers de la version téléchargée.

## 2. Installer sur le disque interne

1. débrancher tous les câbles réseau du CWWK ;
2. brancher écran, clavier et clé USB ;
3. démarrer sur la clé en mode UEFI ;
4. dans l’environnement live, se connecter avec `installer` et le mot de passe
   live indiqué par la documentation officielle ;
5. choisir la disposition clavier voulue ;
6. choisir **ZFS** ;
7. choisir un pool **stripe** pour l’unique disque ;
8. vérifier deux fois le modèle et la capacité du disque interne ;
9. lancer l’installation, qui efface entièrement ce disque ;
10. définir un mot de passe `root` long et unique ;
11. arrêter, retirer la clé USB, puis redémarrer.

Un ZFS stripe à un disque n’apporte aucune redondance. Il est retenu pour ses
contrôles d’intégrité et ses possibilités de reprise ; la vraie protection
reste l’export régulier de `config.xml`.

## 3. Identifier et assigner les deux premiers ports

Depuis la console :

1. utiliser l’assignation des interfaces ;
2. répondre **non** à la création de VLAN ;
3. brancher un câble sur la prise choisie et repérer l’interface qui passe
   `up` ;
4. assigner cette interface à `LAN`, futur rôle `RESCUE` ;
5. répéter avec la prise reliée à la Livebox et l’assigner à `WAN` ;
6. laisser les quatre autres interfaces non assignées ;
7. donner à `LAN/RESCUE` l’adresse `10.10.254.1/24` ;
8. ne configurer ni gateway, ni IPv6, ni serveur DHCP sur `RESCUE`.

Noter hors Git la correspondance entre chaque prise, son adresse MAC et son nom
`igcX`. Étiqueter physiquement `WAN` et `RESCUE`.

## 4. Ouvrir l’administration locale

1. relier directement le PC au port `RESCUE` ;
2. configurer temporairement le PC en `10.10.254.2/24`, sans gateway ni DNS ;
3. ouvrir `https://10.10.254.1` ;
4. accepter uniquement pour cette adresse l’avertissement du certificat local ;
5. se connecter en `root` ;
6. vérifier que l’administration SSH reste désactivée ;
7. conserver la règle anti-lockout sur `RESCUE`.

La WebGUI ne doit jamais être activée sur WAN.

## 5. Raccorder la Livebox

Dans `Interfaces > WAN` :

| Paramètre | Valeur |
|---|---|
| IPv4 Configuration Type | `DHCP` |
| IPv6 Configuration Type | `None` |
| Block private networks | **désactivé** |
| Block bogon networks | **activé** |
| MTU, MSS, vitesse | valeurs automatiques |

`Block private networks` doit être désactivé parce que le WAN reçoit une
adresse privée de la Livebox. Sinon OPNsense bloque son propre upstream.

Ensuite :

1. relier la Livebox au port `WAN` identifié ;
2. vérifier qu’OPNsense obtient une adresse dans le LAN Livebox ;
3. réserver cette adresse dans
   `Livebox > Paramètres avancés > Réseau > DHCP > Baux DHCP statiques` ;
4. vérifier depuis OPNsense l’accès à une IP Internet, la résolution DNS et
   l’heure ;
5. lancer les mises à jour OPNsense et redémarrer si demandé.

Pendant ce bootstrap, OPNsense peut encore utiliser temporairement les DNS
fournis par la Livebox. Ils seront retirés dans le runbook suivant, après la
mise à jour et la synchronisation de l’heure.

Ne créer sur la Livebox ni DMZ vers OPNsense, ni redirection de port, ni UPnP.
Le double NAT est accepté pour ce socle et n’empêche pas les futures connexions
sortantes ou tunnels de Your Cloud.

## 6. Premier checkpoint

Exporter une sauvegarde protégée depuis
`System > Configuration > Backups`, sans statistiques RRD. Ne jamais déposer
le XML en clair dans le dépôt.

Nom de checkpoint conseillé : `opnsense-01-install-wan-rescue`.

## Validation

- `RESCUE` répond sur `https://10.10.254.1` sans WAN ;
- le WAN reçoit toujours la même réservation DHCP après renouvellement ;
- OPNsense atteint Internet et son horloge est synchronisée ;
- aucune règle ou NAT entrant n’existe sur WAN ;
- les quatre autres ports ne fournissent encore aucun réseau ;
- une sauvegarde chiffrée existe hors du firewall.

## Problèmes probables

| Symptôme | Cause probable | Action |
|---|---|---|
| plus d’accès à la Livebox ou OPNsense | conflit `192.168.1.1` | débrancher WAN et remettre `RESCUE` en `10.10.254.1/24` depuis la console |
| WAN DHCP mais pas de trafic | blocage des réseaux privés | désactiver `Block private networks` sur WAN |
| DNS over TLS échouera ensuite | heure incorrecte | corriger fuseau et NTP avant Quad9 |
| une prise ne correspond pas au nom attendu | ordre CWWK différent | refaire le test de lien, ne pas deviner |
| WebGUI perdue | mauvaise assignation | utiliser écran/clavier et réassigner les interfaces |

## Retour arrière

Débrancher le WAN OPNsense. Le Wi-Fi et le LAN Livebox continuent à fournir
l’accès historique. Pour OPNsense, relier le PC directement à `RESCUE` ou
réassigner ce port depuis la console.
