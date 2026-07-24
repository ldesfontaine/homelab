# Choix structurants

Ce fichier fige les décisions importantes sans formalisme d’ADR. Chaque entrée
dit ce qui est retenu, pourquoi et ce que cela implique.

Une décision n’est pas réécrite silencieusement lorsqu’elle change : une
nouvelle entrée la remplace explicitement et explique la raison.

## C-001 — OPNsense devient la frontière du réseau

**Statut : retenu — 23 juillet 2026**

Le câble venant de la Livebox arrive sur le WAN du CWWK. OPNsense assure le
routage, le filtrage et la séparation des réseaux internes.

**Pourquoi :** la Livebox reste nécessaire pour l’accès Orange, mais ne permet
pas la segmentation attendue.

**Conséquence :** aucun équipement du Homelab n’est branché directement entre
la Livebox et le switch interne. Le Wi-Fi Livebox reste temporairement un
réseau séparé, en amont d’OPNsense.

## C-002 — Aucun nouveau matériel réseau

**Statut : retenu — 23 juillet 2026**

Le Netgear MS305E est conservé. Aucun switch supplémentaire n’est prévu ; seul
le futur point d’accès Wi-Fi pourra être acheté.

**Pourquoi :** les six ports du CWWK permettent de sortir Proxmox et le Pi 5 du
switch sans transformer cette contrainte en achat.

**Conséquence :** Proxmox sera relié directement à OPNsense. Le cinquième port
du switch reste disponible pour la future borne Wi-Fi.

## C-003 — Les utilisateurs filaires et le futur Wi-Fi partagent USERS

**Statut : retenu — 23 juillet 2026**

Les deux PC de confiance et le futur SSID principal appartiendront au même
réseau `USERS`.

**Pourquoi :** ils ont le même niveau de confiance et doivent accéder aux mêmes
services sans règles artificiellement différentes.

**Conséquence :** les deux PC restent sur le switch. La borne utilisera plus
tard le dernier port du switch et recevra le VLAN `USERS`.

## C-004 — Le LAB est une zone, pas un bridge

**Statut : retenu — 23 juillet 2026**

Le PC d’expérimentation utilise `LAB-PC` et les futures VM de test utilisent
`LAB-VM`. Les deux réseaux appartiennent à une même zone de sécurité `LAB`.

**Pourquoi :** le PC arrive par le switch tandis que Proxmox arrive par un
autre port OPNsense. Un VLAN unique imposerait un bridge logiciel inutilement
complexe sur le firewall.

**Conséquence :** le PC et les VM pourront communiquer par routage IP lorsque
c’est nécessaire et partageront la même politique de sécurité. Les protocoles
exigeant un domaine de broadcast commun devront être traités comme un besoin
particulier.

## C-005 — Séparer services privés et bordure exposée

**Statut : retenu — 23 juillet 2026**

`SERVICES-PRIVATE` hébergera les applications et données internes. `EDGE`
hébergera uniquement les composants au contact d’Internet ou d’un tunnel
externe.

**Pourquoi :** compromettre un connecteur ou un frontal exposé ne doit pas
donner un accès général aux services et aux données.

**Conséquence :** `EDGE` ne pourra joindre que les adresses et ports de backend
explicitement nécessaires. Ces réseaux restent réservés tant qu’aucun service
n’est déployé.

## C-006 — Le Wi-Fi n’appartient pas à la première partie

**Statut : retenu — 23 juillet 2026**

La Livebox continue à fournir le Wi-Fi. La future borne sera installée
manuellement plus tard.

**Pourquoi :** la borne n’est pas encore disponible et le socle filaire doit
être validable indépendamment.

**Conséquence :** la documentation réserve son port et ses réseaux, sans écrire
de procédure de configuration Wi-Fi.

## C-007 — Le dépôt devient un dossier de reconstruction

**Statut : retenu — 23 juillet 2026**

Le dépôt contient l’état réel, l’architecture, les choix et les runbooks. Le
code Ansible et les procédures de l’ancien Homelab sont retirés de la branche
principale.

**Pourquoi :** conserver du code obsolète à côté de la nouvelle architecture
rendrait ambigu ce qui doit réellement être utilisé.

**Conséquence :** l’ancien état reste accessible dans Git au tag
`ancien-homelab-2026`. Une automatisation ne reviendra que lorsqu’un besoin
réel et validé le justifiera.

## C-008 — Your Cloud observe avant de contrôler

**Statut : retenu pour le Homelab — 23 juillet 2026**

Le réseau doit fonctionner sans Your Cloud. Une future intégration commencera
par l’observation des machines et services.

**Pourquoi :** le Homelab doit rester récupérable et compréhensible même si
Your Cloud est absent ou indisponible.

**Conséquence :** OPNsense reste la source de vérité réseau. Toute capacité de
modification future devra être bornée, explicite, validée et réversible.

## C-009 — Un DNS local, chiffré vers Quad9

**Statut : retenu — 24 juillet 2026**

Les postes utilisent uniquement Unbound sur OPNsense. Unbound transmet les
requêtes en DNS over TLS vers Quad9 Secure.

**Pourquoi :** on obtient un cache local, un transport chiffré et un premier
filtrage des domaines malveillants sans dépendre d’une VM ou d’un service du
Homelab.

**Conséquence :** les DNS directs en ports 53 et 853 sont bloqués pour les
clients. Il n’y a pas de fallback invisible ; la récupération se fait
manuellement par `RESCUE`. Le DNS over HTTPS sur 443 reste une limite connue.

## C-010 — IPv4 seulement pour la première partie

**Statut : retenu — 24 juillet 2026**

Le WAN OPNsense et les réseaux internes sont d’abord configurés en IPv4.

**Pourquoi :** recevoir un préfixe IPv6 derrière la Livebox et reproduire toute
la politique de filtrage ajouterait une seconde architecture à valider avant
même d’avoir prouvé le socle.

**Conséquence :** IPv6 est explicitement désactivé et bloqué dans OPNsense
pendant la partie 1. Son ajout futur sera une décision et une validation
complètes, pas une case activée implicitement.

## C-011 — La gestion du MS305E assume sa limite

**Statut : retenu — 24 juillet 2026**

Le manuel du MS305E ne documente pas de VLAN de management dédié. Son interface
reçoit une IP fixe dans `USERS` et n’est accessible que depuis l’adresse
réservée du poste d’administration.

**Pourquoi :** inventer une fonction absente créerait un faux sentiment
d’isolation. Le switch doit être utilisé sans achat supplémentaire.

**Conséquence :** sa gestion est moins isolée que celle d’un switch pleinement
manageable. L’accès est réduit par sa liste d’autorisation IP, son mot de passe
et le fait qu’il n’est jamais publié. Cette liste IP n’empêche pas un poste
déjà présent dans `USERS` d’usurper l’adresse autorisée ; cela reste accepté car
`USERS` ne contient que des machines de confiance. Le reset physique et l’accès
direct restent le retour arrière.

## C-012 — Commencer sans surcouche de sécurité

**Statut : retenu — 24 juillet 2026**

Suricata, Zenarmor, CrowdSec, les listes DNS publicitaires, UPnP, mDNS, VPN et
les plugins tiers restent désactivés lors de l’installation initiale.

**Pourquoi :** routage, VLAN, DNS, DHCP et règles doivent être observables et
diagnostiquables seuls.

**Conséquence :** une fonction sera ajoutée après la validation du socle, avec
un besoin précis, une mesure de coût et un retour arrière.
