# 03 — Configurer le socle OPNsense

**État : prêt à exécuter, non exécuté**

## Résultat attendu

OPNsense porte les VLAN `USERS` et `LAB-PC`, distribue leurs adresses, fournit
DNS et NTP, chiffre ses requêtes DNS vers Quad9 et applique une politique
d’isolation avant le branchement du switch.

Appliquer chaque section séparément. Tester puis sauvegarder avant de passer à
la suivante.

## 1. Réglages système

Dans `System > Settings > General` :

| Paramètre | Valeur |
|---|---|
| Hostname | `fw` |
| Domain | `home.arpa` |
| Time zone | `Europe/Paris` |
| DNS servers | aucun |
| Allow DNS server list to be overridden by DHCP/PPP on WAN | **désactivé** |
| Do not use the local DNS service as a nameserver | **désactivé** |

`home.arpa` est le domaine réservé par la RFC 8375 aux réseaux domestiques.
Ne pas utiliser `.local`, réservé au mDNS.

Dans `Interfaces > Settings`, désactiver globalement **Allow IPv6**. OPNsense
génère alors aussi une règle de blocage du trafic IPv6 en transit. Ne pas
modifier les options d’offload matériel : aucun IPS n’est installé.

Créer ensuite un compte d’administration nominatif membre du groupe
d’administration, avec un mot de passe différent. Conserver `root` comme
compte de récupération et laisser SSH désactivé.

## 2. Créer les interfaces VLAN

Identifier le port physique étiqueté `TRUNK-SWITCH`. Il reste sans adresse IP
et ne doit pas être assigné comme réseau utilisable.

Dans `Interfaces > Devices > VLAN` :

| Parent | Tag | Description |
|---|---:|---|
| interface physique `TRUNK-SWITCH` | 20 | `VLAN20_USERS` |
| interface physique `TRUNK-SWITCH` | 40 | `VLAN40_LAB_PC` |

Dans `Interfaces > Assignments`, assigner les deux devices puis configurer :

| Interface | IPv4 statique | IPv6 | Block private/bogon |
|---|---|---|---|
| `USERS` | `10.10.20.1/24` | `None` | désactivé |
| `LAB_PC` | `10.10.40.1/24` | `None` | désactivé |

Ne créer dans cette partie ni VLAN 10, 30, 41, 50 ou 60, ni VLAN 4094 côté
OPNsense. Le 4094 est seulement le VLAN natif poubelle du port switch.

## 3. Configurer DHCP avec Dnsmasq

Dans `Services > Dnsmasq DNS & DHCP > General` :

- activer Dnsmasq ;
- sélectionner uniquement `USERS` et `LAB_PC` comme interfaces de service ;
- mettre **Listen Port** à `0` pour désactiver la fonction DNS de Dnsmasq ;
- activer DHCPv4 ;
- laisser DHCPv6 et Router Advertisements désactivés ;
- définir `home.arpa` comme domaine DHCP si le champ est proposé.

Créer les plages :

| Interface | Début | Fin |
|---|---|---|
| `USERS` | `10.10.20.100` | `10.10.20.199` |
| `LAB_PC` | `10.10.40.100` | `10.10.40.199` |

Les clients reçoivent automatiquement `.1` comme gateway et DNS.

Avant d’ouvrir le pool `USERS`, créer une réservation pour le poste
d’administration :

- adresse : `10.10.20.110` ;
- MAC : relevée localement, jamais versionnée ;
- nom : explicite et non sensible.

Ne pas activer DHCP sur `RESCUE` ou un réseau réservé. Les équipements
d’infrastructure recevront des overrides statiques dans Unbound, car Dnsmasq
n’assure pas ici la résolution DNS dynamique des baux.

## 4. Configurer Unbound et Quad9

### Unbound

Dans `Services > Unbound DNS > General` :

- activer Unbound ;
- garder les interfaces d’écoute et de sortie sur `All` ;
- désactiver la validation DNSSEC locale ;
- laisser `Strict QNAME Minimisation` désactivé ;
- ne pas activer `DNS Query Forwarding` ;
- ne pas activer `Use System Nameservers` ;
- laisser les blocklists locales désactivées.

Quad9 Secure réalise la validation DNSSEC. La désactiver dans le forwarder
évite une double validation et de possibles réponses faussement `BOGUS`. Si
Unbound redevient un résolveur récursif autonome un jour, cette décision devra
être revue.

### DNS over TLS

Dans `Services > Unbound DNS > DNS over TLS`, créer deux entrées activées :

| Domain | Server IP | Port | Verify CN |
|---|---|---:|---|
| vide | `9.9.9.9` | 853 | `dns.quad9.net` |
| vide | `149.112.112.112` | 853 | `dns.quad9.net` |

Le domaine vide signifie « toutes les requêtes ». `Verify CN` ne doit jamais
être vide : sans cette vérification, le chiffrement ne prouve pas l’identité du
serveur.

Appliquer, puis :

1. lancer `configctl unbound check` depuis la console ou le shell ;
2. effectuer un DNS Lookup depuis les diagnostics OPNsense ;
3. vérifier que `proto.on.quad9.net` en TXT retourne `dot` ;
4. vérifier que `brokendnssec.net` échoue en `SERVFAIL`.

Le test 3 prouve que Quad9 reçoit la requête en DNS over TLS. Le test 4 prouve
que la réponse DNSSEC invalide est refusée en amont.

### Récupération DNS

Si les IP répondent mais plus aucun nom :

1. accéder à OPNsense par `RESCUE` ;
2. contrôler l’heure, le WAN et les logs Unbound ;
3. désactiver temporairement les deux entrées DNS over TLS ;
4. laisser Unbound résoudre récursivement pour confirmer le diagnostic ;
5. corriger Quad9 ou le temps, puis réactiver les deux entrées.

Ne pas configurer de DNS de secours permanent différent : un fallback
silencieux rendrait le transport et le filtrage imprévisibles.

## 5. Conserver NTP simple

Dans `Services > Network Time > General`, garder le service et les serveurs
`X.opnsense.pool.ntp.org` par défaut. Garder l’écoute sur toutes les interfaces
et limiter l’accès par les règles firewall.

Vérifier que l’état NTP est synchronisé avant de poursuivre.

## 6. Créer les alias firewall

Dans `Firewall > Aliases`, créer :

| Alias | Type | Contenu |
|---|---|---|
| `ADMIN_PC` | Host(s) | `10.10.20.110` |
| `HOME_NETS` | Network(s) | `10.10.0.0/16` et réseau LAN réel de la Livebox |
| `DNS_PORTS` | Port(s) | `53` |
| `DOT_PORT` | Port(s) | `853` |

## 7. Créer les règles

Les règles rapides OPNsense utilisent la première correspondance. Respecter
strictement l’ordre de
[`politique-firewall.md`](../architecture/politique-firewall.md).

Sur `USERS` :

1. autoriser TCP/UDP de `USERS net` vers `USERS address`, `DNS_PORTS` ;
2. autoriser UDP vers `USERS address`, port 123 ;
3. autoriser TCP de `ADMIN_PC` vers `This Firewall`, port 443 ;
4. rejeter et journaliser `USERS net` vers `This Firewall` ;
5. rejeter et journaliser `USERS net` vers `HOME_NETS` ;
6. rejeter et journaliser TCP/UDP vers tous, `DNS_PORTS` ;
7. rejeter et journaliser TCP vers tous, `DOT_PORT` ;
8. autoriser IPv4 de `USERS net` vers tous.

Sur `LAB_PC`, créer le même ordre sans l’autorisation d’administration :

1. DNS local ;
2. NTP local ;
3. rejet journalisé vers `This Firewall` ;
4. rejet journalisé vers `HOME_NETS` ;
5. rejet journalisé du DNS direct en port 53 ;
6. rejet journalisé du DoT direct en port 853 ;
7. autorisation IPv4 vers Internet.

Le service NTP local est disponible, mais le NTP direct n’est pas bloqué dans
la partie 1 : certains postes ignorent les options de temps fournies par DHCP.

Utiliser `Reject` pour les refus internes afin que les tests échouent
rapidement. Ne créer aucune règle WAN.

Dans `Firewall > NAT > Outbound`, conserver le mode **Automatic**. Ne créer
aucun port forward, aucune redirection DNS et aucune règle Livebox.

Sur l’interface `RESCUE`, supprimer les règles par défaut autorisant le transit
LAN vers Internet, mais conserver l’anti-lockout automatique. `RESCUE` sert à
administrer le firewall, pas à contourner sa politique.

## 8. Services volontairement absents

Ne pas activer à ce stade :

- Unbound DNSBL ;
- Suricata ou Zenarmor ;
- CrowdSec ;
- UPnP ;
- mDNS repeater ;
- WireGuard/OpenVPN ;
- API distante, Dynamic DNS ou portail captif.

Ce ne sont pas des oublis. Ils seront ajoutés seulement après la preuve du
socle et un besoin réel.

## Checkpoints

Exporter et chiffrer une sauvegarde après :

1. `opnsense-02-system-vlans-dhcp` ;
2. `opnsense-03-unbound-quad9` ;
3. `opnsense-04-firewall-ready`.

## Validation avant le switch

- `configctl unbound check` réussit ;
- l’heure OPNsense est synchronisée ;
- les VLAN 20 et 40 sont `up` ou sans carrier, sans erreur ;
- le parent du trunk n’a aucune adresse ;
- aucune interface n’existe pour le VLAN poubelle 4094 ;
- aucune règle WAN ou NAT entrant n’existe ;
- `RESCUE` fonctionne toujours après débranchement du WAN ;
- le mode NAT sortant reste automatique.

## Retour arrière

Restaurer le dernier checkpoint depuis
`System > Configuration > Backups`. Si la WebGUI est perdue, les versions
précédentes de `config.xml` restent dans `/conf/backup` et peuvent être
restaurées depuis la console. Ne faire qu’une section entre deux sauvegardes.
