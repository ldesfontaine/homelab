# Cahier des charges — Homelab `ldesfontaine.com`

> **Domaine** : `ldesfontaine.com`<br>
> **FAI** : Orange (fibre 2,5 Gbps, IPv4 statique côté résidentiel)<br>
> **Version du document** : 1.7<br>
> **Statut** : conception validée — prêt pour exécution<br>
> **Auteur** : ldesfontaine

---

## Sommaire

1. [Vision et principes directeurs](#1-vision-et-principes-directeurs)
2. [Inventaire matériel](#2-inventaire-matériel)
3. [Architecture physique](#3-architecture-physique)
4. [Architecture logique](#4-architecture-logique)
5. [Stack technique retenue](#5-stack-technique-retenue)
6. [DNS et certificats](#6-dns-et-certificats)
7. [Authentification et SSO](#7-authentification-et-sso)
8. [Segmentation VLAN détaillée](#8-segmentation-vlan-détaillée)
9. [Matrice firewall OPNsense](#9-matrice-firewall-opnsense)
10. [Stratégie de backup](#10-stratégie-de-backup)
11. [Tunnels VPN](#11-tunnels-vpn)
12. [Plan de mise en œuvre par phases](#12-plan-de-mise-en-œuvre-par-phases)
13. [Procédures de récupération (DR)](#13-procédures-de-récupération-dr)
14. [Concepts critiques](#14-concepts-critiques)
15. [Pièges identifiés à éviter](#15-pièges-identifiés-à-éviter)
16. [Procédures de mise à jour](#16-procédures-de-mise-à-jour)
17. [Procédures opérationnelles (incidents, reboots, coupures)](#17-procédures-opérationnelles-incidents-reboots-coupures)
18. [Stack monitoring (Phase 2)](#18-stack-monitoring-phase-2)

---

## 1. Vision et principes directeurs

### Objectif

Disposer d'une infrastructure d'auto-hébergement robuste pour :

- Servir un portfolio public personnel (haute disponibilité)
- Héberger les services privés sensibles (gestionnaire de mots de passe, partage de fichiers) accessibles à la famille
- Disposer d'un environnement d'expérimentation isolé pour la veille technique et l'apprentissage
- Constituer un terrain de pratique DevOps en conditions réelles (Ansible, Proxmox, OPNsense, monitoring)

### Principes directeurs (non négociables)

1. **Zero trust** — aucun accès administratif direct, ni en local ni à distance. Tout admin transite obligatoirement par tunnel WireGuard. Le port RESCUE physique sur OPNsense est l'unique corde de rappel.

2. **Defense in depth** — segmentation VLAN stricte. Une compromission dans une zone (par exemple le portfolio public) ne doit jamais permettre d'atteindre les zones de plus haute valeur (Authentik, Vaultwarden, PBS).

3. **Souveraineté numérique** — auto-hébergement de toutes les données sensibles. Aucune dépendance à un cloud commercial pour la donnée.

4. **Open source first** — solutions libres préférées en toutes circonstances. Aucun produit propriétaire fermé si une alternative open source de qualité existe.

5. **Infrastructure as Code** — tout déploiement via Ansible. Aucune configuration manuelle non documentée. Chaque rôle Ansible est versionné et testable.

6. **Documentation = source de vérité** — si non documenté, n'existe pas. Toute décision architecturale, mot de passe, secret est tracé dans le repo de documentation (les secrets via Ansible vault ou Vaultwarden, jamais en clair dans Git).

7. **Backup 3-2-1** — minimum trois copies des données, sur deux supports distincts, dont une offsite (cold backup amovible).

8. **Test de restore obligatoire et trimestriel** — un backup non testé n'existe pas.

---

## 2. Inventaire matériel

### Équipements réseau

| Équipement | Modèle | Rôle | Spécifications clés |
|---|---|---|---|
| Modem / box FAI | LiveBox 6 (Orange) | **Aucun port forward, aucun DMZ Host** | Fibre 2,5 Gbps — mode bridge non disponible — admin externe via tunnel sortant WG-ADMIN-RELAY vers VPS (cf. section 11) |
| Pare-feu / routeur | CWWK N150 fanless | OPNsense bare-metal | 6 ports 2,5G, refroidissement passif |
| Switch | Netgear MS305E | Distribution L2 + VLAN tagging | 5 ports 2,5G, web managed |
| Point d'accès WiFi | UniFi U6 Lite | Diffusion SSIDs multi-VLAN | WiFi 6, alimenté en PoE |

### Équipements compute

| Équipement | Modèle | Rôle | Spécifications clés |
|---|---|---|---|
| Hyperviseur | Mini PC | Proxmox VE 8 — VMs et LXCs | 32 Go RAM, 8 cœurs, 2× SSD |
| Serveur de backup | Raspberry Pi 5 | Proxmox Backup Server | 16 Go RAM, 2× NVMe en ZFS mirror, UPS HAT |
| VPS frontal | Hetzner CX22 (cible) | Pangolin + portfolio + CrowdSec | 4 Go RAM, 2 vCPU, ~5 €/mois |

### Postes utilisateurs et IoT

| Équipement | Rôle | VLAN |
|---|---|---|
| PC gaming 1 | Poste personnel | 20 (LAN) |
| PC gaming 2 | Poste personnel | 20 (LAN) |
| Laptop | Mobile + admin (avec WG-ADMIN-RELAY client) | 20 (LAN) |
| Téléphones | Devices mobiles | 20 (LAN, WiFi) |
| Caméra IP | Surveillance | 30 (IOT, WiFi) |
| Chauffage connecté | Domotique | 30 (IOT, WiFi) |

### Stockage et clés

| Support | Rôle | Chiffrement |
|---|---|---|
| 2× NVMe Pi5 | Datastore PBS principal (ZFS mirror) | LUKS + datastore PBS chiffré |
| Disque externe 1 To | Cold backup amovible offsite | LUKS |
| Papier coffre / parents | Sauvegarde ultime des clés (master password Vaultwarden, clé PBS, clé LUKS) | n/a — physique |

---

## 3. Architecture physique

### Schéma physique

<svg width="100%" viewBox="0 0 680 620" role="img" xmlns="http://www.w3.org/2000/svg">
<title>Schéma physique du homelab ldesfontaine</title>
<desc>Topologie physique : Internet via fibre Orange arrive sur LiveBox 6 qui fonctionne en simple modem (aucun port forward, aucun DMZ Host). OPNsense N150 est connecté sur son port WAN. OPNsense distribue par ses 6 ports vers le switch Netgear MS305E (trunk), le mini PC Proxmox (trunk), et le Pi5 PBS (VLAN 99). Un port RESCUE est laissé volontairement vide pour les pannes. Le switch dessert l'AP UniFi U6 Lite en trunk pour les SSIDs WiFi, et trois postes en VLAN 20. Un VPS Hetzner externe héberge Pangolin, le portfolio statique, CrowdSec et le hub WireGuard WG-ADMIN-RELAY pour l'admin externe.</desc>
<defs>
<marker id="arrow-p" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#888780" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker>
</defs>
<rect x="60" y="30" width="160" height="50" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text x="140" y="48" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">Internet</text>
<text x="140" y="66" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">Fibre Orange 2,5G</text>
<rect x="460" y="30" width="160" height="50" rx="8" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
<text x="540" y="48" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#3C3489">VPS Hetzner</text>
<text x="540" y="66" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#534AB7">Pangolin + portfolio + CrowdSec</text>
<line x1="140" y1="80" x2="140" y2="110" stroke="#888780" stroke-width="1"/>
<rect x="60" y="110" width="160" height="50" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text x="140" y="128" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">LiveBox 6</text>
<text x="140" y="146" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">Modem only</text>
<line x1="140" y1="160" x2="140" y2="200" stroke="#888780" stroke-width="1"/>
<rect x="40" y="200" width="600" height="100" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="340" y="222" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#0C447C">OPNsense — CWWK N150 fanless</text>
<text x="340" y="240" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">Routage, firewall, VLANs, WG-ADMIN-RELAY, Unbound DNS, CrowdSec</text>
<text x="100" y="282" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">P1 WAN</text>
<text x="200" y="282" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">P2 trunk</text>
<text x="300" y="282" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">P3 trunk</text>
<text x="400" y="282" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">P4 VLAN 99</text>
<text x="500" y="282" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">P5 RESCUE</text>
<text x="585" y="282" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">P6 spare</text>
<line x1="200" y1="300" x2="140" y2="340" stroke="#888780" stroke-width="1"/>
<line x1="300" y1="300" x2="360" y2="340" stroke="#888780" stroke-width="1"/>
<line x1="400" y1="300" x2="560" y2="340" stroke="#888780" stroke-width="1"/>
<rect x="40" y="340" width="200" height="60" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="140" y="362" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#0C447C">Switch MS305E</text>
<text x="140" y="380" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">5 ports 2,5G — VLAN aware</text>
<rect x="260" y="340" width="200" height="60" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="360" y="362" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#0C447C">Mini PC Proxmox</text>
<text x="360" y="380" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">32 Go, 8 cœurs — LXC + VM</text>
<rect x="480" y="340" width="160" height="60" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="560" y="362" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#0C447C">Pi 5 — PBS</text>
<text x="560" y="380" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">2 NVMe ZFS mirror</text>
<line x1="80" y1="400" x2="80" y2="440" stroke="#888780" stroke-width="1"/>
<line x1="120" y1="400" x2="210" y2="440" stroke="#888780" stroke-width="1"/>
<line x1="160" y1="400" x2="330" y2="440" stroke="#888780" stroke-width="1"/>
<line x1="200" y1="400" x2="460" y2="440" stroke="#888780" stroke-width="1"/>
<rect x="20" y="440" width="120" height="50" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="80" y="458" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#0C447C">AP UniFi U6</text>
<text x="80" y="476" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">SSID multi-VLAN</text>
<rect x="160" y="440" width="100" height="50" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text x="210" y="458" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">PC gaming 1</text>
<text x="210" y="476" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">VLAN 20</text>
<rect x="280" y="440" width="100" height="50" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text x="330" y="458" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">PC gaming 2</text>
<text x="330" y="476" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">VLAN 20</text>
<rect x="400" y="440" width="120" height="50" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text x="460" y="458" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">Laptop</text>
<text x="460" y="476" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">VLAN 20 + WG admin</text>
<line x1="80" y1="490" x2="80" y2="510" stroke="#B4B2A9" stroke-width="0.5" stroke-dasharray="2 2"/>
<rect x="20" y="510" width="240" height="90" rx="8" fill="none" stroke="#B4B2A9" stroke-width="0.5" stroke-dasharray="4 4"/>
<text x="140" y="530" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">Clients WiFi (via AP)</text>
<text x="140" y="554" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">Téléphones, laptop sans fil — VLAN 20</text>
<text x="140" y="572" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">Switch console — VLAN 20</text>
<text x="140" y="590" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">Caméra, chauffage — VLAN 30 IOT</text>
</svg>

### Affectation des ports OPNsense (CWWK N150, 6 ports)

| Port | Usage | VLAN(s) | Note |
|---|---|---|---|
| P1 | WAN | n/a (interface WAN) | Vers LiveBox 6, IP statique côté LiveBox — sortie Internet uniquement, **aucun port forward entrant** |
| P2 | LAN trunk | tagged 10, 20, 30 | Vers switch Netgear MS305E port 1 |
| P3 | Compute trunk | tagged 10, 50, 60, 70 | Vers Mini PC Proxmox |
| P4 | BACKUP | untagged 99 | Vers Pi5 PBS (port unique dédié) |
| P5 | RESCUE | untagged 192.168.99.0/24 | **Désactivé en exploitation, câble débranché**. À utiliser uniquement en cas de catastrophe |
| P6 | Spare | non assigné | Réserve future |

### Affectation des ports switch Netgear MS305E (5 ports)

| Port | Usage | Mode | Note |
|---|---|---|---|
| P1 | Uplink trunk vers OPNsense | tagged 10, 20, 30 | Trunk |
| P2 | PC gaming 1 | untagged 20 | Access |
| P3 | PC gaming 2 | untagged 20 | Access |
| P4 | Laptop (filaire) | untagged 20 | Access |
| P5 | AP UniFi U6 Lite | tagged 10, 20, 30 | Trunk pour SSIDs multi-VLAN |

---

## 4. Architecture logique

### Schéma logique

<svg width="100%" viewBox="0 0 680 760" role="img" xmlns="http://www.w3.org/2000/svg">
<title>Schéma logique du homelab — VLANs et services</title>
<desc>Architecture logique segmentée en 7 VLANs avec OPNsense comme passerelle et firewall. Externe : visiteurs Internet, Cloudflare DNS, et VPS Hetzner avec Pangolin/CrowdSec/portfolio. Tunnel WG-PUB depuis VPS vers Newt dans le VLAN EXPOSED. OPNsense gère firewall, routage VLAN, endpoint WG-ADMIN-RELAY, Unbound DNS split-horizon, Suricata IDS. VLANs trustés : MGMT, LAN, SVC_PRIV (Authentik IDP central), BACKUP isolé. VLANs restreints : EXPOSED (Newt uniquement), IOT, LAB.</desc>
<defs>
<marker id="arrow-l" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#888780" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker>
<marker id="arrow-purple" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="#7F77DD" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker>
</defs>
<rect x="40" y="20" width="180" height="60" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text x="130" y="42" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">Internet (public)</text>
<text x="130" y="60" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">Visiteurs portfolio + famille</text>
<rect x="240" y="20" width="180" height="60" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text x="330" y="42" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#444441">Cloudflare DNS</text>
<text x="330" y="60" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#5F5E5A">*.ldesfontaine.com → VPS</text>
<rect x="440" y="20" width="200" height="60" rx="8" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
<text x="540" y="42" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#3C3489">VPS Hetzner — Pangolin</text>
<text x="540" y="60" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#534AB7">Traefik + portfolio + CrowdSec</text>
<line x1="130" y1="80" x2="130" y2="130" stroke="#888780" stroke-width="1" marker-end="url(#arrow-l)"/>
<path d="M 540 80 V 100 H 660 V 290 H 640" stroke="#7F77DD" stroke-width="1.5" stroke-dasharray="6 4" fill="none" marker-end="url(#arrow-purple)"/>
<text x="600" y="94" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#534AB7">WG-PUB</text>
<rect x="40" y="130" width="600" height="100" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="340" y="152" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="14" font-weight="500" fill="#0C447C">OPNsense — passerelle et firewall</text>
<text x="340" y="170" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">Routage inter-VLAN — firewall stateful — CrowdSec</text>
<text x="160" y="198" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">WG-ADMIN-RELAY</text>
<text x="160" y="214" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">UDP/51820</text>
<text x="340" y="198" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">Unbound DNS</text>
<text x="340" y="214" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">split-horizon + blocklists</text>
<text x="520" y="198" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">Suricata IDS</text>
<text x="520" y="214" text-anchor="middle" dominant-baseline="central" font-family="sans-serif" font-size="12" fill="#185FA5">trafic ciblé WAN</text>
<rect x="40" y="250" width="280" height="100" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="60" y="272" font-family="sans-serif" font-size="14" font-weight="500" fill="#0C447C">VLAN 10 — MGMT</text>
<text x="60" y="292" font-family="sans-serif" font-size="12" fill="#185FA5">10.10.10.0/24</text>
<text x="60" y="316" font-family="sans-serif" font-size="12" fill="#185FA5">• OPNsense GUI, Proxmox host</text>
<text x="60" y="334" font-family="sans-serif" font-size="12" fill="#185FA5">• Switch + AP UniFi (admin)</text>
<rect x="360" y="250" width="280" height="100" rx="8" fill="#FAECE7" stroke="#993C1D" stroke-width="0.5"/>
<text x="380" y="272" font-family="sans-serif" font-size="14" font-weight="500" fill="#712B13">VLAN 50 — EXPOSED (DMZ)</text>
<text x="380" y="292" font-family="sans-serif" font-size="12" fill="#993C1D">10.10.50.0/24</text>
<text x="380" y="316" font-family="sans-serif" font-size="12" fill="#993C1D">• LXC Newt — terminus WG-PUB</text>
<text x="380" y="334" font-family="sans-serif" font-size="12" fill="#993C1D">(portfolio hébergé sur le VPS)</text>
<rect x="40" y="370" width="280" height="100" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="60" y="392" font-family="sans-serif" font-size="14" font-weight="500" fill="#0C447C">VLAN 20 — LAN</text>
<text x="60" y="412" font-family="sans-serif" font-size="12" fill="#185FA5">10.10.20.0/24</text>
<text x="60" y="436" font-family="sans-serif" font-size="12" fill="#185FA5">• PC gaming, laptop, téléphones</text>
<text x="60" y="454" font-family="sans-serif" font-size="12" fill="#185FA5">• Switch console, WiFi famille</text>
<rect x="360" y="370" width="280" height="100" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="380" y="392" font-family="sans-serif" font-size="14" font-weight="500" fill="#0C447C">VLAN 60 — SVC_PRIV</text>
<text x="380" y="412" font-family="sans-serif" font-size="12" fill="#185FA5">10.10.60.0/24</text>
<text x="380" y="436" font-family="sans-serif" font-size="12" fill="#185FA5">• Authentik (IDP) + Traefik interne</text>
<text x="380" y="454" font-family="sans-serif" font-size="12" fill="#185FA5">• Vaultwarden, Filebrowser-Quantum</text>
<rect x="40" y="490" width="280" height="100" rx="8" fill="#FAECE7" stroke="#993C1D" stroke-width="0.5"/>
<text x="60" y="512" font-family="sans-serif" font-size="14" font-weight="500" fill="#712B13">VLAN 30 — IOT</text>
<text x="60" y="532" font-family="sans-serif" font-size="12" fill="#993C1D">10.10.30.0/24</text>
<text x="60" y="556" font-family="sans-serif" font-size="12" fill="#993C1D">• Caméra IP, chauffage connecté</text>
<text x="60" y="574" font-family="sans-serif" font-size="12" fill="#993C1D">• Internet OK — LAN deny strict</text>
<rect x="360" y="490" width="280" height="100" rx="8" fill="#FAECE7" stroke="#993C1D" stroke-width="0.5"/>
<text x="380" y="512" font-family="sans-serif" font-size="14" font-weight="500" fill="#712B13">VLAN 70 — LAB</text>
<text x="380" y="532" font-family="sans-serif" font-size="12" fill="#993C1D">10.10.70.0/24</text>
<text x="380" y="556" font-family="sans-serif" font-size="12" fill="#993C1D">• LXC Wazuh, expérimentations</text>
<text x="380" y="574" font-family="sans-serif" font-size="12" fill="#993C1D">• Sandbox isolé du reste</text>
<rect x="40" y="610" width="600" height="80" rx="8" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="60" y="632" font-family="sans-serif" font-size="14" font-weight="500" fill="#0C447C">VLAN 99 — BACKUP</text>
<text x="60" y="652" font-family="sans-serif" font-size="12" fill="#185FA5">10.10.99.0/24 — strictement isolé</text>
<text x="60" y="676" font-family="sans-serif" font-size="12" fill="#185FA5">• PBS sur Pi5 (ZFS mirror) · cold backup amovible chiffré offsite</text>
<rect x="40" y="715" width="14" height="14" rx="3" fill="#E6F1FB" stroke="#185FA5" stroke-width="0.5"/>
<text x="62" y="725" font-family="sans-serif" font-size="12" fill="#185FA5">Trusted</text>
<rect x="140" y="715" width="14" height="14" rx="3" fill="#FAECE7" stroke="#993C1D" stroke-width="0.5"/>
<text x="162" y="725" font-family="sans-serif" font-size="12" fill="#993C1D">Restreint / exposé</text>
<rect x="290" y="715" width="14" height="14" rx="3" fill="#EEEDFE" stroke="#534AB7" stroke-width="0.5"/>
<text x="312" y="725" font-family="sans-serif" font-size="12" fill="#534AB7">Externe à nous</text>
<rect x="430" y="715" width="14" height="14" rx="3" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
<text x="452" y="725" font-family="sans-serif" font-size="12" fill="#5F5E5A">Externe non contrôlé</text>
</svg>

---

## 5. Stack technique retenue

| Couche | Solution | Justification |
|---|---|---|
| Hyperviseur | Proxmox VE 8 | Open source, mature, KVM + LXC, écosystème Ansible riche |
| Pare-feu / routeur | OPNsense (bare metal) | Fork pfSense activement maintenu, plugins solides, support Suricata + CrowdSec |
| Containers légers | LXC sur Proxmox | Privilégiés pour services système (moins d'overhead que VM) |
| Containers applicatifs | Docker (dans LXC ou VPS) | Pour les apps multi-services (Pangolin, CrowdSec) |
| OS hôtes (LXC + VPS) | Debian 13 (Trixie) | Stable, standardisation, support Ansible long terme |
| Frontal public | Pangolin (Fossorial) | Tunneling sécurisé sortant, gestion ressources, certs LE auto, OIDC client |
| Reverse proxy public | Traefik (embarqué dans Pangolin) | + plugin CrowdSec bouncer |
| Reverse proxy interne | Traefik (LXC dans SVC_PRIV) | Cert wildcard via DNS-01 Cloudflare |
| Identité (IDP) | Authentik (single instance) | Source de vérité utilisateurs et MFA, OIDC provider |
| Gestionnaire mots de passe | Vaultwarden | Compatible Bitwarden, OIDC officiel mergé upstream |
| Partage fichiers | Filebrowser-Quantum | Léger, support OIDC |
| Backup | Proxmox Backup Server (PBS) | Intégration native Proxmox, dédup, chiffrement |
| DNS récursif local | Unbound (sur OPNsense) | Recursive resolver + split-horizon + blocklists |
| DNS public | Cloudflare | Gratuit, API stable, **proxy off**, **WAF off** |
| Tunnel admin | WireGuard sur OPNsense | Léger, performant, intégré OPNsense |
| Tunnel public | WireGuard via Newt (Pangolin) | Client officiel Pangolin, sortant uniquement |
| Synchro horloge | chrony (sur tous LXCs/VMs/VPS) | OIDC dépend de timestamps UTC cohérents — dérive > 30s = `invalid_token` (cf. concept 14.7) |
| Automatisation | Ansible | Source de vérité de la conf, repo Git privé |
| Monitoring (phase 2) | Prometheus + Grafana | Standard de fait, intégrations Proxmox/OPNsense |
| IDS / parefeu IP | Suricata sur OPNsense + CrowdSec (VPS et OPNsense) | Détection menaces réseau et IP malveillantes |

---

## 6. DNS et certificats

### Stratégie DNS

#### DNS public (Internet)

- Hébergé chez **Cloudflare** (registrar et DNS, plan free)
- Enregistrements :
  - `ldesfontaine.com` → IP du VPS Hetzner (record **A** + **AAAA**)
  - `*.ldesfontaine.com` → IP du VPS Hetzner (record **A** + **AAAA** wildcard)
- **Proxy Cloudflare désactivé** (orange cloud OFF, mode "DNS only")
- **WAF Cloudflare désactivé** — la protection se fait via CrowdSec sur VPS
- Token API Cloudflare scoped : `Zone:DNS:Edit` sur la zone uniquement, stocké en secret Ansible vault

> **Note dual-stack** : le VPS Hetzner est dual-stack natif (IPv4 + IPv6 routé). Les records AAAA pointent vers l'IPv6 du VPS, ce qui permet aux visiteurs en IPv6 (~40% du trafic résidentiel européen en 2026) d'accéder directement aux services publics sans passage par 6to4. Le tunnel WG-PUB Newt → VPS reste en IPv4 (puisque la maison est IPv4-only via la LiveBox qui ne délègue pas de préfixe IPv6 propre, cf. concept 14.8 et piège correspondant en section 15).

#### DNS interne (LAN et VLANs)

- **Unbound sur OPNsense** en mode **recursive resolver** (pas de forwarder vers Google/CF)
- Listening sur les interfaces VLAN internes
- **Split-horizon** : overrides locaux pour `*.ldesfontaine.com` → IPs internes (Traefik dans SVC_PRIV)
- Blocklists chargées : StevenBlack hosts + OISD basic
- DNSSEC activé

### Stratégie certificats

#### Cert wildcard partagé public + interne

- Génération via **Let's Encrypt**, challenge **DNS-01** (API Cloudflare)
- Couverture : `ldesfontaine.com` + `*.ldesfontaine.com`
- Une instance LE sur Pangolin (VPS) pour le frontal public
- Une instance LE sur Traefik interne (LXC dans SVC_PRIV) pour le frontal interne — utilise le même token API Cloudflare
- Renouvellement automatique des deux côtés

> **Pourquoi le même nom wildcard partout ?** Avec le split-horizon DNS, `vault.ldesfontaine.com` résout en interne vers Traefik interne et en externe vers le VPS. Le cert wildcard est valide dans les deux cas. Pas de PKI privée à gérer, pas de cert auto-signé qui te fait cliquer sur "advanced" dans le navigateur.

---

## 7. Authentification et SSO

### Architecture d'identité

- **Authentik est l'unique source de vérité** pour les comptes utilisateurs et les facteurs d'authentification
- Single-instance, LXC Debian 13 dans VLAN SVC_PRIV, avec PostgreSQL local au LXC
- MFA TOTP **forcée pour tous les comptes** (politique Authentik)
- Pas de fallback SMS, pas d'email magic link

### Chaîne SSO (OIDC)

Authentik est OIDC provider pour :

| Client OIDC | Rôle | Politique |
|---|---|---|
| Pangolin (sur VPS) | Authentification au "gate" Pangolin | Login + MFA |
| Vaultwarden | SSO Vaultwarden (officiel mergé upstream mi-2025) | Login + MFA, master password en plus |
| Filebrowser-Quantum | SSO Filebrowser | Login + MFA |
| Authentik UI (self-service) | Modification MFA, mot de passe | Login + MFA |

> **Proxmox n'est PAS branché à Authentik**. C'est délibéré pour éviter une dépendance circulaire : si Authentik est cassé, tu dois pouvoir le réparer en accédant à Proxmox. L'auth admin Proxmox reste 100% locale (login + TOTP Proxmox).

### Flux d'authentification — visiteur public sur le portfolio

1. Visiteur → DNS Cloudflare → IP du VPS
2. HTTPS vers VPS → Pangolin/Traefik
3. Pangolin route `portfolio.ldesfontaine.com` → container nginx local sur le VPS (sert fichiers statiques)
4. Pas d'authentification, contenu public

### Flux d'authentification — famille accède à Vaultwarden

1. Famille → DNS Cloudflare → IP du VPS
2. HTTPS vers VPS → Pangolin
3. Pangolin route `vault.ldesfontaine.com` — ressource protégée par Pangolin Gate
4. Redirection HTTPS vers Authentik via tunnel WG-PUB → Newt → SVC_PRIV → Authentik
5. Authentik affiche login + demande TOTP
6. Validation → cookie SSO posé → redirection vers `vault.ldesfontaine.com`
7. Vaultwarden détecte le cookie OIDC → utilisateur loggé côté SSO
8. Saisie du master password Vaultwarden (déverrouille la clé du coffre chiffré côté client)
9. Accès au coffre

### Flux d'authentification — admin (toi)

1. Activation du client WireGuard ADMIN sur le laptop (split-tunnel quotidien ou full-tunnel "PARANO")
2. Tunnel monte vers OPNsense (UDP/51820 sur IP publique de la maison)
3. Tu tapes `proxmox.ldesfontaine.com`
4. Unbound (OPNsense) résout via split-horizon → IP interne MGMT
5. Le paquet est sourcé depuis 10.99.10.X (subnet WG-ADMIN-RELAY)
6. OPNsense firewall : src=WG-ADMIN-RELAY, dst=MGMT → ALLOW
7. HTTPS Proxmox UI → auth Proxmox locale (login + TOTP Proxmox)

> **Important** : ce flux fonctionne aussi quand tu es physiquement sur le LAN à la maison. Le client WG sort vers ton IP publique (via la LiveBox), revient et termine sur OPNsense. La latence ajoutée est négligeable.

---

## 8. Segmentation VLAN détaillée

| ID | Nom | Subnet | Catégorie | Trust | Contenu | Internet | Inter-VLAN |
|---|---|---|---|---|---|---|---|
| 10 | MGMT | 10.10.10.0/24 | Administration | Élevée | OPNsense GUI, Proxmox host, switch, AP admin, LXC UniFi controller | Updates uniquement | Accessible depuis WG-ADMIN-RELAY seulement |
| 20 | LAN | 10.10.20.0/24 | Postes utilisateurs | Moyenne | PC gaming, laptop, téléphones (WiFi famille), switch console | OK | Accès SVC_PRIV via Traefik :443 uniquement |
| 30 | IOT | 10.10.30.0/24 | Objets connectés | Faible | Caméra IP, chauffage connecté | Limité (HTTPS, DNS, NTP) | Aucun |
| 50 | EXPOSED | 10.10.50.0/24 | DMZ logique | Faible | LXC Newt (terminus tunnel WG-PUB) | Vers VPS uniquement (UDP/51820) + updates HTTPS | SVC_PRIV via Traefik :443 |
| 60 | SVC_PRIV | 10.10.60.0/24 | Services privés | Élevée | LXC Authentik, Vaultwarden, Filebrowser, Traefik interne | Limité (LE, OIDC callbacks, updates) | Aucun |
| 70 | LAB | 10.10.70.0/24 | Sandbox | Faible | LXC Wazuh, expérimentations | Limité (updates) | Aucun |
| 99 | BACKUP | 10.10.99.0/24 | Backup isolé | Élevée | Pi5 PBS (ZFS mirror) | Limité (updates) | Aucun |

---

## 9. Matrice firewall OPNsense

### Politique générale

- **Politique par défaut** : DENY ALL — toute règle non listée est implicitement bloquée
- **Connexions established/related** : ALLOW (state tracking automatique d'OPNsense)
- **Stratégie dual-stack** : OPNsense conserve le support IPv6 activé. La maison est IPv4-only en pratique (la LiveBox derrière laquelle on opère ne délègue pas de préfixe v6 propre, cf. piège correspondant en section 15). Les règles utilisent un alias unifié couvrant les deux familles, pour qu'aucune modif ne soit nécessaire le jour où IPv6 deviendra fonctionnel (passage en PPPoE direct ou évolution Orange).
- **Alias `PRIVATE_NETS`** créé regroupant :
  - v4 : `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (RFC 1918)
  - v6 : `fc00::/7` (Unique Local Addresses RFC 4193), `fe80::/10` (link-local)

  Cet alias couvre **tout ce qui est privé** dans les deux stacks. Internet par construction n'y est pas. À utiliser à la place de `any` chaque fois qu'on veut dire "Internet uniquement, pas inter-VLAN" (voir [section 14.1](#141-le-piège-de-any-et-lalias-private_nets)).
- **Alias `VPS_PANGOLIN`** créé pour les IPs **v4 + v6** statiques du VPS Hetzner (à mettre à jour si changement de VPS)

### Règles par interface source

#### WAN (Internet inbound)

| Destination | Service | Action | Note |
|---|---|---|---|
| * | * | DENY | **Aucun port ouvert depuis Internet.** Tous les tunnels (WG-PUB, WG-ADMIN-RELAY, WG-MON) sont sortants depuis la maison. La LiveBox ne forwarde rien. |

#### Sortant depuis OPNsense (interface WAN egress)

| Destination | Service | Action | Note |
|---|---|---|---|
| VPS_PANGOLIN | udp/51821 | ALLOW | Tunnel sortant WG-ADMIN-RELAY (OPNsense → hub VPS) |
| !PRIVATE_NETS | tcp/80, tcp/443, udp/53, udp/123 | ALLOW | Updates OPNsense, NTP, DNS resolveurs upstream |
| * | * | DENY | Default deny |

#### WG-ADMIN-RELAY (10.99.10.0/24) — interface wg-admin-client côté OPNsense

| Destination | Service | Action | Note |
|---|---|---|---|
| MGMT | any | ALLOW | Admin Proxmox, OPNsense, switch, AP |
| BACKUP | any | ALLOW | Admin PBS |
| SVC_PRIV | tcp/22, tcp/443 | ALLOW | SSH + HTTPS sur LXCs |
| LAB | any | ALLOW | Sandbox admin |
| 192.168.1.1 | tcp/80, tcp/443 | ALLOW | Admin LiveBox |
| !PRIVATE_NETS | any | ALLOW | Mode PARANO full-tunnel (Internet via maison) |
| * | * | DENY | Tout le reste |

#### MGMT (10.10.10.0/24)

| Destination | Service | Action | Note |
|---|---|---|---|
| !PRIVATE_NETS | tcp/80, tcp/443, udp/53 | ALLOW | Updates Proxmox + OPNsense + LXCs |
| BACKUP | tcp/8007 | ALLOW | Proxmox host → PBS (backups quotidiens) |
| * | * | DENY | Default zero-trust |

#### LAN (10.10.20.0/24)

| Destination | Service | Action | Note |
|---|---|---|---|
| OPNsense (Unbound) | tcp/53, udp/53 | ALLOW | Résolution DNS interne |
| !PRIVATE_NETS | any | ALLOW | Internet (surf, jeux, etc.) |
| SVC_PRIV (Traefik interne) | tcp/443 | ALLOW | Accès direct services via split-horizon |
| 192.168.1.1 | * | DENY | Admin LiveBox refusé depuis LAN |
| PRIVATE_NETS | * | DENY | Toute autre destination privée bloquée |

#### IOT (10.10.30.0/24)

| Destination | Service | Action | Note |
|---|---|---|---|
| !PRIVATE_NETS | tcp/443, tcp/80, udp/53, udp/123 | ALLOW | Internet limité (HTTPS, DNS, NTP) |
| PRIVATE_NETS | * | DENY | Aucune communication interne |

#### EXPOSED (10.10.50.0/24) — cage stricte pour Newt

| Destination | Service | Action | Note |
|---|---|---|---|
| VPS_PANGOLIN | UDP/51820 | ALLOW | Tunnel WG-PUB sortant maintenu |
| OPNsense (Unbound) | tcp/53, udp/53 | ALLOW | DNS interne |
| !PRIVATE_NETS | tcp/443 | ALLOW | Updates HTTPS uniquement (Docker, apt) |
| SVC_PRIV (Traefik interne) | tcp/443 | ALLOW | Forward Pangolin → services internes |
| * | * | DENY | Tout autre trafic refusé |

#### SVC_PRIV (10.10.60.0/24)

| Destination | Service | Action | Note |
|---|---|---|---|
| !PRIVATE_NETS | tcp/80, tcp/443, udp/53 | ALLOW | LE, OIDC callbacks, updates |
| PRIVATE_NETS | * | DENY | Aucune connexion interne sortante |

#### LAB (10.10.70.0/24)

| Destination | Service | Action | Note |
|---|---|---|---|
| !PRIVATE_NETS | tcp/443, udp/53 | ALLOW | Updates HTTPS limités |
| PRIVATE_NETS | * | DENY | Sandbox totalement isolé |

#### BACKUP (10.10.99.0/24)

| Destination | Service | Action | Note |
|---|---|---|---|
| !PRIVATE_NETS | tcp/443, udp/53, udp/123 | ALLOW | Updates PBS, NTP |
| PRIVATE_NETS | * | DENY | Strictement isolé |

---

## 10. Stratégie de backup

### Principe 3-2-1

- **3 copies** : production (Proxmox) + PBS principal (Pi5 ZFS mirror) + cold backup amovible
- **2 supports distincts** : NVMe Pi5 et disque externe USB
- **1 offsite** : disque cold tournant entre domicile et lieu sûr (parents)

### Architecture backup détaillée

| Niveau | Localisation | Type | Fréquence | Chiffrement |
|---|---|---|---|---|
| 1 — Production | Mini PC Proxmox | LXCs et VMs vivants | n/a | sur disque (LUKS optionnel) |
| 2 — Backup principal | Pi5 PBS | ZFS mirror sur 2× NVMe | Quotidien automatique | LUKS + datastore PBS chiffré |
| 3 — Cold backup | Disque externe 1 To | Datastore PBS sync | Hebdomadaire manuel + après changement majeur | LUKS |

### Politique de rétention PBS

- 7 backups quotidiens
- 4 backups hebdomadaires
- 6 backups mensuels
- Garbage collection PBS hebdomadaire automatique

### Backup des équipements réseau et configs critiques

Les équipements réseau ne sont **pas** sauvegardés via PBS (qui ne gère que VMs/LXCs). Stratégie dédiée pour pouvoir reconstruire l'infra réseau de zéro :

| Élément | Méthode | Fréquence | Cible |
|---|---|---|---|
| OPNsense `config.xml` | API `/api/core/backup/download/this` via Ansible (rôle `config-backup`) | Quotidien | LXC `config-backup` → PBS |
| Switch MS305E | Export config web manuel | Après chaque changement de VLAN/PVID | Repo Git `docs/configs/` |
| UniFi Network App (controller) | Auto-backup natif sur volume du LXC | Quotidien (mécanisme natif) | Couvert par backup LXC PBS |
| AP UniFi U6 Lite | n/a — conf 100% pilotée par controller | n/a | Couvert par backup controller |
| Cert wildcard (`acme.json`) | Inclus dans le backup LXC Traefik interne | Quotidien | Couvert par backup LXC PBS |
| Repo Git Ansible/docs | Mirror local (`git clone --mirror`) cron quotidien | Quotidien | LXC dédié → PBS |

> **Note** : sur OPNsense, à terme, la collection Ansible `ansibleguy.opnsense` permet de gérer la conf en IaC pur — la config n'est plus *backupée*, elle est **régénérée** depuis le repo Git. Cible phase 2.

### Gestion des clés de chiffrement

| Clé | Stockage primaire | Stockage de secours |
|---|---|---|
| Master password Vaultwarden | Mémoire (toi) + cache mobile chiffré | Papier offline (chez parents) |
| Clé de chiffrement datastore PBS | Vaultwarden | Papier offline (chez parents) |
| Clé LUKS disque cold | Vaultwarden | Papier offline (chez parents) |
| Tokens API Cloudflare | Vaultwarden + Ansible vault | n/a |

### Tests de restore — non négociables

- **Trimestriel** : restauration test d'un LXC depuis PBS sur un environnement de test
- **Annuel** : DR complet — reconstruction d'Authentik depuis le cold backup, hors Proxmox principal
- **Documentation** : chaque test consigné dans le repo doc avec date, durée, anomalies

---

## 11. Tunnels VPN

Trois tunnels coexistent dans l'archi, **tous sortants depuis la maison** (zéro port ouvert sur la LiveBox) :

### WG-ADMIN-RELAY (administration zero-trust via VPS hub)

**Principe** : pour ne pas exposer la maison sur Internet, le tunnel d'admin externe ne se termine pas en écoute directe sur la LiveBox. À la place :

- Le **VPS Hetzner** héberge un **hub WireGuard** qui écoute UDP/51821 publiquement (le VPS est de toute façon sur Internet)
- **OPNsense** est un **peer sortant** du VPS — il initie une connexion vers le VPS au démarrage et la maintient via `PersistentKeepalive = 25`
- Le **laptop admin** est un autre peer du VPS
- Le VPS active `net.ipv4.ip_forward=1` et **forwarde** le trafic entre les peers

```
Laptop admin (4G, hôtel, n'importe où)
    │ WG client (sortant vers VPS)
    │ UDP/51821 vers VPS public IP
    ▼
┌─────────────────────────────────────────┐
│ VPS Hetzner                             │
│   • Pangolin (services publics)         │
│   • WG hub UDP/51821                    │
│     Subnet 10.99.10.0/24                │
│     net.ipv4.ip_forward=1               │
│     Forwarding entre peers              │
└──────────────────┬──────────────────────┘
                   │ trafic admin forwardé
                   │ via tunnel sortant
                   ▼
┌─────────────────────────────────────────┐
│ OPNsense (bare-metal N150)              │
│   • Client WG sortant vers VPS          │
│     wg-admin-client interface           │
│   • Route 10.99.10.0/24 → wg-interface  │
│   • PAS d'écoute UDP entrante           │
└──────────────────┬──────────────────────┘
                   │ accès aux VLANs internes selon matrice
                   ▼
              MGMT, SVC_PRIV, BACKUP, etc.
```

#### Paramètres clés

- **Port VPS** : UDP/51821 (51820 reste réservé pour Newt/Pangolin → séparation claire)
- **Subnet relay** : 10.99.10.0/24
- **IP OPNsense côté tunnel** : 10.99.10.2
- **IP laptop côté tunnel** : 10.99.10.10
- **PersistentKeepalive** : 25s côté OPNsense ET côté laptop (essentiel pour traverser NAT LiveBox)

#### Profils clients

**Profil "quotidien" (split-tunnel)** :
```ini
AllowedIPs = 10.10.10.0/24, 10.10.60.0/24, 10.10.70.0/24, 10.10.99.0/24, 192.168.1.1/32
```

**Profil "PARANO" (full-tunnel)** :
```ini
AllowedIPs = 0.0.0.0/0
```
Sur WiFi public — tout le trafic est routé via la maison (sortie Internet via OPNsense → LiveBox).

#### Clients autorisés

- Laptop admin (config primaire)
- Phone admin (à activer en déplacement)
- Tablet admin (optionnel)

#### Trade-offs assumés

- ✅ **Zéro port ouvert** sur la LiveBox côté maison
- ✅ **IP maison invisible** des scans Shodan/Censys
- ✅ Termination sur OPNsense bare-metal (pas de dépendance Proxmox)
- ✅ Cohérence parfaite avec WG-PUB (même pattern : tout sortant)
- ⚠️ **VPS = SPOF pour l'admin externe** (panne Hetzner = pas d'admin distant pendant la panne)
- ⚠️ Latence admin +30-50 ms (négligeable pour SSH/web UI)

**Mitigations du SPOF VPS** :
- **Port RESCUE physique** sur OPNsense P5 reste toujours disponible (ultime fallback en local)
- Reconstruction VPS via Ansible en ~30 min en cas de crash dur
- Hetzner SLA 99,9% = ~8h max de panne par an, en pratique nettement moins
- Option future : second VPS chez un autre provider (Scaleway, OVH) en cold standby si paranoïa

> **Cohérence architecturale** : ce tunnel admin **suit le même principe** que le tunnel public WG-PUB (Newt → VPS) — tout est sortant depuis la maison vers le VPS. Le VPS est la **seule** surface d'exposition publique de tout l'écosystème.

### WG-PUB (tunneling Pangolin pour services publics)

- Direction : **sortant uniquement** depuis Newt LXC (VLAN EXPOSED) → VPS Hetzner
- **Point de terminaison côté maison** : le **LXC Newt** dans VLAN EXPOSED, **et lui seul** (pas OPNsense, pas un Newt par service — voir concept critique 14.8 pour la justification détaillée)
- Géré automatiquement par Newt (client officiel Pangolin), pas de config WireGuard manuelle
- **Aucun port forward** depuis l'extérieur n'est nécessaire (la connexion est initiée depuis la maison)
- Subnet : géré par Pangolin (transparent)
- Port VPS : UDP/51820 (Pangolin), distinct de WG-ADMIN-RELAY (UDP/51821)

### WG-MON (scrape monitoring du VPS — phase 16)

- Voir [section 18.4](#184-scraping-du-vps-hetzner--tunnel-wg-mon-dédié) pour le détail
- Direction : sortant depuis LXC monitoring → VPS
- Port VPS : UDP/51822
- Subnet : 10.99.0.0/30
- Activé uniquement en phase 16 (monitoring), pas avant

### Récap des ports VPS publiquement exposés

| Port | Protocole | Service | Direction |
|---|---|---|---|
| 22 | TCP | SSH (clé uniquement, fail2ban) | Entrant |
| 80 | TCP | HTTP (redirect 443) | Entrant |
| 443 | TCP | HTTPS (Pangolin/Traefik intégré) | Entrant |
| 51820 | UDP | WG-PUB (Pangolin/Newt) | Entrant (peer maison) |
| 51821 | UDP | WG-ADMIN-RELAY (hub d'admin) | Entrant (peers laptop + OPNsense) |
| 51822 | UDP | WG-MON (scrape monitoring, phase 16) | Entrant (peer LXC monitoring) |

Le VPS reste hardé : SSH key-only, UFW restrictif, CrowdSec actif, mises à jour automatiques sécu uniquement (cf. section 16).

---

## 12. Plan de mise en œuvre par phases

### Stratégie de mise en œuvre échelonnée

> **Insight architectural fondamental** : l'archi a été pensée pour que **aucun port ne soit ouvert sur la LiveBox**. Absolument **tous** les flux d'admin et de services publics passent par des **tunnels sortants** depuis la maison vers le VPS Pangolin (WG-PUB pour les services publics via Newt, WG-ADMIN-RELAY pour l'admin externe via OPNsense en client sortant). Conséquence : on peut construire 100% du homelab sans jamais toucher la config publique de la LiveBox. La LiveBox reste un simple modem fibre tout au long du projet, du jour 1 jusqu'à la production finale.

Le déploiement se fait en **4 blocs séquentiels** :

| Bloc | Quand | Phases concernées | LiveBox |
|---|---|---|---|
| **A — Construction interne** | Première période, ~3-4 semaines | 0, 1, 2 (sans AP), 3, 4 (sans test 4G), 5, 6 (sans AP), 7, 8, 9, 10, 11, 12, 13 | Inchangée — primaire, WiFi up, aucun port forward |
| **B — Arrivée de l'AP** | Quand l'AP UniFi est livré, ~½ jour | Finalisation Phase 2 (câblage AP, trunk) + Phase 6 (adoption AP, SSIDs réels) | Inchangée |
| **C — Activation publique** | Après bloc B validé, ~½ jour | Finalisation Phase 4 (validation du tunnel WG-ADMIN-RELAY depuis 4G) | Inchangée — **toujours aucun port forward**, l'admin externe passe par le tunnel sortant OPNsense → VPS |
| **D — Bascule production** | Après bloc C, ~1 jour | Phase 14 (sous-étapes onboarding famille + migration WiFi) + Phase 15 (hardening final) | WiFi LiveBox désactivé en fin |

Pendant tout le **bloc A**, le réseau LiveBox 192.168.1.0/24 reste **le réseau primaire** de la famille. Le homelab nait comme un **sous-réseau** : OPNsense est un client de la LiveBox (IP fixe `192.168.1.2`), il route et firewall ses propres VLANs en interne, mais n'est pas atteignable depuis Internet (LiveBox firmware closed). La famille continue à utiliser son WiFi LiveBox pour Internet, sans rien voir du chantier en cours.

> **Conséquence pratique** : les phases ci-dessous décrivent l'**état final** de chaque livrable, mais certaines validations ("test depuis 4G", "AP intégré", "famille sur SSID UniFi") sont **différées** au bloc B, C ou D selon le cas. Chaque phase concernée le précise explicitement.

### Phase 0 — Préparation (~½ jour)

**Livrables**
- Repo Git privé (GitHub/GitLab/Forgejo) avec structure : `docs/`, `ansible/{inventory,roles,playbooks}/`
- VPS Hetzner provisionné (Debian 13 minimal, SSH key only, firewall cloud Hetzner activé)
- Compte Cloudflare avec domaine `ldesfontaine.com`, token API généré et stocké
- Vault de transition (Bitwarden hosted) pour les secrets initiaux

**Validation** : `git push` et `ssh root@vps` fonctionnent. Le domaine résout via `dig`.

### Phase 1 — OPNsense bare-metal (~1 jour)

> **Bloc A — sans toucher la LiveBox.** Pendant toutes les phases 1 à 13, l'**ancien réseau LiveBox reste actif** (WiFi LiveBox up, PC gaming et phones connectés dessus, Internet OK pour la famille). OPNsense devient un client de la LiveBox en `192.168.1.2`, route ses propres VLANs en interne, mais **n'est pas joignable depuis Internet** (LiveBox firewall fermé, **aucun port forward activé**). La bascule complète et la désactivation du WiFi LiveBox interviennent dans le bloc D (phase 14), après validation complète.

**Livrables**
- OPNsense installé sur N150 (USB d'install, partition unique, root sur SSD interne)
- IP statique côté LiveBox (`192.168.1.2/24`, GW `192.168.1.1`) — **réservation DHCP** dans la LiveBox, aucun port forward activé
- LiveBox configurée :
  - Mot de passe admin changé (long, unique, dans Vaultwarden cible)
  - Admin distant désactivé
  - UPnP désactivé
  - **WiFi LiveBox CONSERVÉ** (sera désactivé en phase 14, après migration des utilisateurs vers AP UniFi)
  - DHCP statique pour `192.168.1.2` (réservation OPNsense)
  - **Aucun port forward, aucun DMZ Host, ni maintenant ni plus tard.** L'admin externe passera par le tunnel sortant WG-ADMIN-RELAY (OPNsense → VPS), configuré en Phase 4. La LiveBox reste un simple modem fibre tout au long de la vie de l'infra.
- OPNsense : interfaces WAN (192.168.1.2 vers LiveBox) et LAN par défaut configurées, GUI admin accessible en interne uniquement

**Validation (interne uniquement)**
- Console OPNsense accessible localement
- Depuis OPNsense, `ping 1.1.1.1` fonctionne (sortie Internet via LiveBox NAT OK)
- Depuis OPNsense, résolution DNS fonctionne (`dig google.com`)
- GUI OPNsense accessible depuis un PC branché en LAN par défaut
- OPNsense **n'est PAS joignable** depuis Internet (LiveBox closed)

> **Le test "depuis 4G externe" est différé au bloc C**, après mise en place du tunnel WG-ADMIN-RELAY (Phase 9 côté VPS + Phase 4 côté OPNsense). À ce stade Phase 1, on valide uniquement la connexion locale à OPNsense.

### Phase 2 — VLANs + switch (~1 jour) — *AP différé au bloc B*

> **Bloc A — AP non encore disponible.** L'AP UniFi U6 Lite n'est pas encore livré (~1 mois d'attente). Cette phase couvre **uniquement** la partie switch + VLANs OPNsense. Le câblage et l'adoption de l'AP sont **finalisés au bloc B** (sous-étape 14.a) à son arrivée. Le port switch P5 (trunk pour AP) est **préparé maintenant** pour qu'il n'y ait plus qu'à brancher le PoE le jour J.

**Livrables (bloc A — maintenant)**
- VLANs 10/20/30/50/60/70/99 créés sur OPNsense (interfaces, DHCP server, gateways)
- Switch MS305E configuré (PVID + VLAN tagging par port selon section 3)
- **Port switch P5 préconfiguré en trunk** pour l'AP futur (tous VLANs taggés sauf 10 qui peut servir de PVID management si l'AP support, sinon adapter selon doc UniFi)
- Port RESCUE configuré sur OPNsense P5 (`192.168.99.0/24`, désactivé tant que pas branché)

**Livrables différés (bloc B — à l'arrivée AP)**
- Câblage AP UniFi sur switch P5 (PoE)
- Adoption AP dans UniFi controller (cf. Phase 6)
- SSIDs réels poussés sur l'AP (cf. Phase 6)

**Validation (bloc A uniquement)**
- Un device de test (laptop câblé en P3 du switch, par exemple) en VLAN 30 obtient une IP correcte, sort vers Internet, mais ne peut pas pinguer une IP en VLAN 10
- Routage inter-VLAN OK selon matrice firewall
- **Aucune validation WiFi** à ce stade (AP absent)

### Phase 3 — Unbound DNS (~2h)

**Livrables**
- Unbound activé sur OPNsense (recursive resolver, pas de forwarder)
- Blocklists StevenBlack hosts + OISD basic chargées
- Overrides locaux pour `*.ldesfontaine.com` → IPs internes (à compléter au fur et à mesure)

**Validation** : `dig portfolio.ldesfontaine.com @10.10.20.1` retourne IP interne. Test pub bloquée sur un site connu.

### Phase 4 — WireGuard ADMIN-RELAY côté OPNsense (~3h) — *activation effective différée au bloc C*

> **Bloc A — Préparation côté OPNsense uniquement.** Le tunnel admin externe est un **relay via VPS** : OPNsense initie une connexion **sortante** vers un hub WireGuard sur le VPS, sur lequel le laptop admin est aussi un peer. Phase 4 prépare la **partie OPNsense** (client sortant + clés + règles firewall) ainsi que les profils laptop, mais le hub côté VPS sera créé en **Phase 9** (avec Pangolin). La validation complète depuis 4G est différée au **bloc C** (sous-étape 14.b).
>
> **Important** : pas de serveur WireGuard en écoute sur OPNsense. Pas de port UDP entrant. OPNsense est un **client WireGuard sortant**, comme le laptop le sera depuis l'extérieur.

**Livrables (bloc A — maintenant)**
- Génération des paires de clés WireGuard :
  - OPNsense client (sera peer du hub VPS)
  - Laptop admin (sera peer du hub VPS)
  - Phone admin (sera peer du hub VPS)
  - Tablet admin si applicable
- Plan d'adressage subnet relay : `10.99.10.0/24`
  - VPS hub : 10.99.10.1
  - OPNsense : 10.99.10.2
  - Laptop : 10.99.10.10
  - Phone : 10.99.10.11
  - Tablet : 10.99.10.12
- Pré-configuration **interface WireGuard client** sur OPNsense (instance "WG-ADMIN-CLIENT"), mais **non activée** tant que le hub VPS n'existe pas (Phase 9). Conf en attente :
  ```ini
  [Interface]
  Address = 10.99.10.2/24
  PrivateKey = <opnsense_priv>

  [Peer]
  PublicKey = <vps_pub>           # à renseigner après Phase 9
  Endpoint = <vps_pub_ip>:51821   # à renseigner après Phase 9
  AllowedIPs = 10.99.10.0/24
  PersistentKeepalive = 25
  ```
- Profils clients laptop et phone générés (split-tunnel + PARANO), en attente d'activation post-Phase 9
- Règles firewall WG-ADMIN-RELAY préparées sur OPNsense (selon section 9), pour autoriser le trafic depuis l'interface wg-admin-client vers MGMT, SVC_PRIV, BACKUP, etc.
- Clés privées stockées dans Ansible Vault (jamais en clair dans Git)

**Validation (bloc A — interne uniquement)**
- Toutes les paires de clés sont générées et stockées de manière chiffrée
- La configuration OPNsense est en place (interface inactive, peer placeholder)
- Aucune erreur de syntaxe dans les `.conf` clients
- Documentation à jour dans le repo (liste des IPs, peers, clés publiques)

> **Activation et validation au bloc C (sous-étape 14.b)** : une fois le hub VPS opérationnel (Phase 9), on renseigne la clé publique et l'endpoint du VPS dans la conf OPNsense, on active l'interface, et on teste depuis 4G : le laptop admin se connecte au VPS, le tunnel monte, ping `10.10.10.1` OK. Sans WG, aucun ping ne passe (LiveBox totalement fermée).

### Phase 5 — Proxmox bare-metal (~1 jour)

**Livrables**
- Proxmox VE 8 sur mini PC, branché sur OPNsense P3
- Bridge Linux VLAN-aware (`vmbr0` avec `bridge-vlan-aware yes`)
- IP MGMT statique (ex. `10.10.10.20`)
- Premier rôle Ansible `proxmox-host` créé pour idempotence

**Validation** : Proxmox UI accessible **uniquement** via WG-ADMIN-RELAY (une fois activé en bloc C) ou via le réseau MGMT en local. Test depuis VLAN 20 sans WG → connexion refusée.

### Phase 6 — LXC UniFi controller (~2h) — *adoption AP différée au bloc B*

> **Bloc A — AP non encore disponible.** L'install du controller et la pré-configuration des SSIDs se font maintenant. L'AP sera adopté à son arrivée (sous-étape 14.a, bloc B).

**Livrables (bloc A — maintenant)**
- LXC Debian 13 dans VLAN MGMT
- UniFi Network Application installée (via Ansible)
- SSIDs **pré-configurés** sous forme de templates (pas encore poussés sur AP, qui n'existe pas encore) :
  - "Maison" → VLAN 20 (WPA3, partagé famille)
  - "IoT" → VLAN 30 (WPA2/3, restrictif)
- Politiques WiFi définies (puissance émission, bandes, isolation client, etc.)

**Livrables différés (bloc B — à l'arrivée AP)**
- AP UniFi U6 Lite câblé sur switch P5 (PoE)
- Adoption AP dans UniFi controller
- Push des SSIDs pré-configurés sur l'AP
- Test fonctionnel SSIDs avec un device de test (sans migrer la famille)

**Validation (bloc A uniquement)**
- UI UniFi controller accessible via WG-ADMIN-RELAY
- Les SSIDs sont visibles dans la conf (en attente de device)
- Le controller est en attente d'adoption d'un AP

> **Validation différée au bloc B (sous-étape 14.a)** : un laptop de test se connecte à "Maison", IP en VLAN 20, accès Internet OK ; une caméra de test connectée à "IoT" est en VLAN 30, ne voit pas le LAN. **Les utilisateurs réels (PC gaming, phones famille) restent sur le WiFi LiveBox jusqu'à la sous-étape 14.d.**

### Phase 7 — LXC services privés (~1 jour)

**Livrables**
- LXC Authentik (Debian 13) dans SVC_PRIV avec PostgreSQL local
- LXC Vaultwarden dans SVC_PRIV
- LXC Filebrowser-Quantum dans SVC_PRIV
- Compte admin Authentik créé avec MFA TOTP active
- Rôles Ansible créés pour chaque service

**Validation** : via WG-ADMIN-RELAY, accès aux UIs des trois services.

### Phase 8 — Reverse proxy interne + cert wildcard (~2h)

**Livrables**
- LXC Traefik dans SVC_PRIV
- Cert wildcard `*.ldesfontaine.com` généré via DNS-01 Cloudflare API (resolver acme Traefik)
- Routage : `vault.ldesfontaine.com` → Vaultwarden, `files.ldesfontaine.com` → Filebrowser, `auth.ldesfontaine.com` → Authentik
- Override Unbound mis à jour pour pointer vers Traefik interne

**Validation** : depuis LAN (split-horizon DNS), `https://vault.ldesfontaine.com` répond avec cert valide.

### Phase 9 — VPS Pangolin + portfolio + CrowdSec + WG hub admin (~6h)

> **Pourquoi CrowdSec dès la phase 9 et pas plus tard** : à la minute où tu fais pointer le DNS Cloudflare vers le VPS, `portfolio.ldesfontaine.com` est scanné par les bots dans les heures qui suivent. Sans CrowdSec, tu prends en pleine face tous les scans `/wp-admin`, `/.env`, `/.git/config`, scans CVE Apache, etc. Pas dramatique pour un nginx statique, mais pollue les logs et t'expose pour rien. **On déploie CrowdSec dans la même session que Pangolin, avant de basculer le DNS.**
>
> **Pourquoi WG hub admin aussi en Phase 9** : le tunnel WG-ADMIN-RELAY a besoin que le hub VPS existe pour que OPNsense puisse s'y connecter. On le pose dans la même session que Pangolin, sur le **même VPS** (port distinct UDP/51821), pour cohérence et simplicité opérationnelle.

**Ordre d'exécution dans la session** :

1. **Hardening de base du VPS** (avant tout) :
   - UFW activé : ports 22, 80, 443, 51820, 51821 entrants (en v4 et v6)
   - fail2ban SSH installé
   - Login SSH par mot de passe désactivé (clé uniquement)
   - Mises à jour à jour, `unattended-upgrades` configuré sécu-only
2. **Docker Engine** installé sur le VPS
3. **Pangolin** déployé via Docker Compose officiel
4. **Container nginx** servant le portfolio statique (volume monté sur les fichiers HTML)
5. **CrowdSec** déployé en container aux côtés de Pangolin :
   - Bouncer Traefik configuré (plugin Pangolin)
   - Scenarios : `crowdsecurity/http-cve`, `crowdsecurity/http-bf`, `crowdsecurity/http-probing`
6. **WG hub admin** (WireGuard natif sur le VPS, hors Docker) :
   - Génération de la paire de clés VPS
   - Conf `/etc/wireguard/wg-admin.conf` :
     ```ini
     [Interface]
     Address = 10.99.10.1/24
     ListenPort = 51821
     PrivateKey = <vps_priv>
     PostUp = sysctl -w net.ipv4.ip_forward=1
     PostUp = iptables -A FORWARD -i %i -j ACCEPT
     PostDown = iptables -D FORWARD -i %i -j ACCEPT

     [Peer]
     # OPNsense maison
     PublicKey = <opnsense_pub>
     AllowedIPs = 10.99.10.2/32, 10.10.10.0/24, 10.10.60.0/24, 10.10.70.0/24, 10.10.99.0/24

     [Peer]
     # Laptop admin
     PublicKey = <laptop_pub>
     AllowedIPs = 10.99.10.10/32

     [Peer]
     # Phone admin
     PublicKey = <phone_pub>
     AllowedIPs = 10.99.10.11/32
     ```
   - `systemctl enable --now wg-quick@wg-admin`
   - Vérification : `wg show wg-admin` montre les peers déclarés (sans connexion encore, normal)
7. **Records DNS Cloudflare** A + AAAA + wildcard pointent vers VPS (= moment où le portfolio devient public). À cet instant, CrowdSec est déjà actif.
8. **Certs Let's Encrypt** générés par Pangolin (DNS-01)
9. **Pangolin déclare** la ressource `portfolio.ldesfontaine.com` → `http://nginx-portfolio:80` local

**Validation** :
- `https://portfolio.ldesfontaine.com` répond depuis 4G avec cert valide. Pas d'auth, contenu visible.
- Test CrowdSec : depuis 4G, lancer un script qui spam un faux endpoint sensible (ex. `/.env`, `/wp-login.php`). L'IP source doit être bannie au bout de quelques tentatives. `cscli decisions list` la confirme.
- `wg show wg-admin` sur VPS liste les peers configurés (la validation effective du tunnel arrive en bloc C 14.b)

> **Note sécurité** : la clé privée WireGuard du VPS reste stockée localement sur le VPS (jamais commitée en clair). Le bootstrap du VPS via Ansible la **génère** lors du premier `playbook run`, et stocke uniquement sa **clé publique** dans le vault Ansible pour distribution aux autres peers.

### Phase 10 — LXC Newt + tunnel WG-PUB (~1h)

> **C'est quoi Newt** : Newt est le **client officiel de tunneling** de Pangolin. C'est un petit binaire (Go, distribué en Docker) qui tourne **chez toi**, dans le LXC EXPOSED. Il initie une connexion WireGuard **sortante** depuis chez toi vers le VPS Pangolin, et la maintient ouverte avec keepalive et reconnexion auto. Quand un visiteur tape `vault.ldesfontaine.com`, le VPS reçoit la requête et la **rebalance dans le tunnel** vers Newt, qui forwarde vers Traefik interne (LXC SVC_PRIV) → service final.
>
> **C'est le seul point de terminaison du tunnel chez toi** (cf. concept critique 14.8). Pas de Newt par service, pas de Newt sur OPNsense — un seul, dans une cage stricte.
>
> **Statut "connecté" dans l'UI Pangolin** : Pangolin affiche pour chaque "site" déclaré un indicateur 🟢 connecté ou 🔴 déconnecté, basé sur l'état du tunnel WireGuard et les keepalives. C'est l'équivalent du statut "online/offline" d'un agent dans n'importe quel outil de tunneling. Tant que c'est rouge, aucune ressource ne peut être routée à travers ce site.

**Livrables**
- LXC Debian 13 dans VLAN EXPOSED
- Newt installé via Docker (image officielle), token Pangolin et endpoint VPS configurés en variables d'environnement
- Le tunnel WG-PUB monte automatiquement au démarrage du container
- Logs Newt vérifiés : `docker logs newt` montre la connexion établie

**Validation** : dans l'UI Pangolin sur le VPS, le site "home" est listé comme **🟢 connecté**. Coupure test (`docker stop newt`) → le statut passe à 🔴 dans la minute. Redémarrage → repasse 🟢.

### Phase 11 — Publication ressources + OIDC (~1 jour)

**Livrables**
- Ressources Pangolin déclarées : `vault.ldesfontaine.com`, `files.ldesfontaine.com`, `auth.ldesfontaine.com`
- Cibles configurées : routage via tunnel WG-PUB → Newt → Traefik interne → service final
- Authentik configuré comme provider OIDC pour Pangolin Gate (politique : login + MFA)
- Authentik configuré comme provider OIDC pour Vaultwarden et Filebrowser (clients OIDC dans Authentik avec scopes `openid profile email`)
- Bouton OIDC visible sur les login pages

**Validation** : test bout en bout depuis 4G avec un compte famille de test. Login Authentik → MFA → ouverture Vaultwarden → master password → coffre accessible.

### Phase 12 — PBS Pi5 + backup automatique (~1 jour)

> *(Anciennement phase 13 — la phase CrowdSec dédiée a été fusionnée dans la phase 9.)*

**Livrables**
- PBS installé sur Pi5 Debian 13, branché P4 OPNsense en VLAN 99
- ZFS mirror sur 2× NVMe (`zpool create backup mirror /dev/nvme0n1 /dev/nvme1n1`)
- Datastore PBS chiffré (clé sauvée Vaultwarden + papier offline immédiatement)
- Proxmox host configure datastore PBS comme cible
- Schedule backup quotidien (toutes VMs et LXCs critiques, rétention selon section 10)

**Validation** : un backup tourne et termine OK. Restore test : LXC Authentik restauré sur nouveau VMID dans Proxmox → service remonte fonctionnel.

### Phase 13 — Cold backup amovible (~2h)

> *(Anciennement phase 14.)*

**Livrables**
- Disque externe 1 To formaté LUKS, label `cold-backup-01`
- Datastore PBS additionnel sur le disque cold (montable/démontable)
- Procédure documentée :
  1. Brancher disque
  2. Décrypter LUKS
  3. Sync via PBS (`proxmox-backup-client sync`)
  4. Démonter LUKS
  5. Débrancher et stocker hors site
- Procédure inverse (restore depuis cold) testée et documentée

**Validation** : test concret de restore depuis le disque cold sur une machine vierge.
### Phase 14 — Bascule en production (~1 à 1,5 jour cumulé)

> **Phase pivot qui regroupe les blocs B, C et D**. À déclencher **après** :
> - Tout le bloc A est validé et stable depuis au moins quelques jours
> - L'AP UniFi est physiquement livré
> - Tu as documenté ton repo Git proprement (ADRs à jour, runbooks écrits)
>
> Cette phase contient **4 sous-étapes** à enchaîner dans l'ordre. Chacune valide un cap, on n'enchaîne sur la suivante qu'une fois la précédente stable.

#### Phase 14.a — Bloc B : arrivée AP, finalisation Phase 2 + Phase 6 (~½ jour)

**Livrables**
- AP UniFi U6 Lite branché sur switch P5 (PoE)
- AP adopté dans UniFi controller (cf. doc UniFi)
- SSIDs pré-configurés en Phase 6 poussés sur l'AP (Maison + IoT)
- Test fonctionnel avec un device de test (laptop ou phone perso uniquement, **pas la famille**)

**Validation**
- Le laptop de test se connecte à "Maison", obtient une IP en VLAN 20, accès Internet OK
- Un phone connecté à "IoT" est en VLAN 30, ne voit pas le LAN
- Les utilisateurs réels (famille) **restent sur le WiFi LiveBox** — bascule famille différée à 14.d

#### Phase 14.b — Bloc C : activation du tunnel WG-ADMIN-RELAY + validation depuis 4G (~½ jour)

> **À ne déclencher que quand 14.a est validé et qu'OPNsense + VPS sont stables depuis plusieurs jours.** Cette sous-étape ne touche **plus du tout à la LiveBox** : la LiveBox reste à 100% fermée, comme depuis le début. On active uniquement le tunnel sortant OPNsense → VPS, et on valide depuis 4G.

**Livrables**
- Côté OPNsense :
  - Renseignement de la clé publique du VPS et de son endpoint (`<vps_pub_ip>:51821`) dans la conf wg-admin-client préparée en Phase 4
  - Activation de l'interface WireGuard cliente (sortante)
  - Vérification : `wg show` montre le tunnel monté, le dernier handshake date de quelques secondes
- Côté VPS :
  - Vérification que les peers OPNsense, laptop et phone sont bien tous déclarés
  - `wg show wg-admin` montre OPNsense connecté
- Côté laptop admin :
  - Profil WG distribué et activé (split-tunnel et/ou PARANO selon usage)
  - Premier test : depuis 4G, activer le tunnel et tenter un ping vers `10.10.10.1`

**Validation**
- Depuis 4G, le tunnel monte côté laptop → ping `10.10.10.1` (OPNsense MGMT) OK
- Test SSH depuis 4G vers OPNsense via `10.10.10.1` : connexion réussie
- Test UI Proxmox depuis 4G via `https://10.10.10.20:8006` : accessible
- Sans activer le tunnel, ping `<IP publique LiveBox>` ne donne **strictement rien** (LiveBox fermée à 100%, aucun port ouvert)
- L'admin de OPNsense, Proxmox, services internes est accessible **uniquement** via le tunnel relay

> **Au moment de cette sous-étape**, les services publics (portfolio, vault, files, etc.) sont déjà accessibles depuis Internet (depuis la Phase 11 via le tunnel WG-PUB Pangolin/Newt). L'activation de WG-ADMIN-RELAY **n'ouvre rien de plus** côté Internet — c'est juste un canal supplémentaire **sortant** depuis OPNsense, transparent pour le scanner externe.

> **Résultat sécurité** : la LiveBox est totalement fermée (aucun port, aucune réponse à un scan), l'IP publique maison n'apparaît dans **aucune** liste Shodan/Censys avec un service exploitable. La seule surface publique de toute l'archi est le VPS Hetzner, qui est de toute façon sur Internet par nature.

> **Trade-off assumé** : le VPS devient un SPOF pour l'admin distant. En cas de panne VPS, l'admin externe est temporairement inaccessible. **Mitigations** :
> - Port RESCUE physique sur OPNsense (P5) reste l'ultime fallback **toujours disponible** quand on est sur place
> - Hetzner SLA 99,9% (~8h/an max de panne, en pratique négligeable)
> - Procédure de reconstruction VPS via Ansible documentée en section 13 (~30 min)

#### Phase 14.c — Bloc D, partie 1 : onboarding famille (~1h par personne)

> Pré-requis : 14.a et 14.b validés. Tu peux confirmer toi-même depuis 4G que toute la chaîne (Pangolin → tunnel → Authentik → Vaultwarden) fonctionne, et que WG-ADMIN-RELAY externe marche.

**Livrables**
- Comptes Authentik créés pour chaque membre famille
- MFA TOTP forcée à la première connexion (politique Authentik)
- Master password Vaultwarden généré aléatoirement (32 chars), transmis sur canal séparé (papier en main propre, ou Signal)
- Email de bienvenue avec URLs (`vault.ldesfontaine.com`, `files.ldesfontaine.com`) et procédure premier login
- Coffre Vaultwarden initialisé avec quelques entrées de démo
- Premier login validé en présence physique pour chaque membre (avec setup MFA)

**Validation**
- Chaque membre famille se connecte sur `vault.ldesfontaine.com`, passe Authentik + MFA, déverrouille son coffre Vaultwarden
- Personne ne s'est planté sur la création MFA (le piège classique : on enregistre l'app authenticator mais on perd les codes de secours)

#### Phase 14.d — Bloc D, partie 2 : migration WiFi LiveBox → UniFi (~½ jour)

> Pré-requis : 14.c validé. Annonce préalable à la famille **24h avant** : "demain on change le WiFi, voici le nouveau nom de réseau et le nouveau mot de passe, ça prendra 5 minutes par device."

**Livrables**
- Bascule des devices **un par un** sur le SSID "Maison" UniFi (PC gaming, phones famille, tablettes, laptop)
- Vérification que chaque device fonctionne normalement (Internet, latence OK, applications quotidiennes inchangées)
- Bascule des devices IoT (caméra, chauffage) sur le SSID "IoT" UniFi → VLAN 30
- **Désactivation du WiFi LiveBox** (admin LiveBox → désactiver radio 2,4 GHz et 5 GHz)
- Vérification finale : aucun device n'est plus connecté à la LiveBox WiFi

**Validation**
- Plus aucun client WiFi visible côté LiveBox (vérifiable dans l'UI LiveBox)
- Tous les devices sont dans le bon VLAN (vérifiable côté UniFi controller et OPNsense DHCP leases)
- Pendant 24-48h, surveiller les retours famille — toute panne ou ralentissement → diagnostic et correction
- Si problème majeur, **fallback rapide** : réactiver le WiFi LiveBox en 2 min depuis l'admin LiveBox

> **À ce stade, l'infra est en production complète.** La LiveBox ne sert plus que de modem fibre (NAT sortant vers Internet). **Aucun port forward, aucun DMZ Host, aucune entrée publique.** Toute l'admin et tous les services publics passent par les tunnels sortants WG-PUB et WG-ADMIN-RELAY vers le VPS Hetzner.

### Phase 15 — Hardening final + audit (~1 jour)

> *(Anciennement phase 16.)*

**Livrables**
- CrowdSec installé sur OPNsense (plugin) + bouncer firewall — protège les ports exposés (UDP 51820)
- Suricata sur OPNsense, surveille trafic WAN entrant + EXPOSED sortant
- Audit règles firewall : relire la config actuelle vs matrice section 9, supprimer toute règle obsolète/non documentée
- Test de DR complet documenté : reconstruction d'Authentik depuis backup PBS

**Validation** : test DR réussi en moins de 30 minutes. Aucune perte de données.

### Phase 16 — Phase 2 future (variable, après stabilisation 2-3 mois)

> *(Anciennement phase 17.)*
>
> **Architecture détaillée du monitoring : voir [section 18 — Stack monitoring](#18-stack-monitoring-phase-2)**. La présente phase n'est qu'un repère temporel : monitoring déployé seulement une fois l'infra stable depuis 2-3 mois.

Travaux principaux :

- LXC monitoring dédié dans VLAN MGMT (Prometheus + Loki + Grafana + Alertmanager + ntfy)
- Exporters posés via Ansible sur tous les hôtes et services (selon mapping section 18)
- Tunnel WG-MON dédié pour scrape du VPS Hetzner
- Intégration OIDC Authentik pour l'auth Grafana
- Règles firewall additionnelles MGMT → autres VLANs sur ports d'exporters
- Évaluation passage en PPPoE direct pour activer IPv6 routé côté maison (+ 802.1X selon région)

---

## 13. Procédures de récupération (DR)

### Scénario 1 — Compromission Authentik

1. Isoler le LXC Authentik (couper interface réseau via Proxmox)
2. Identifier le vecteur (logs Authentik, logs Traefik, logs CrowdSec)
3. Restaurer un backup Authentik PRÉ-compromission depuis PBS
4. Forcer rotation des secrets MFA pour tous les utilisateurs
5. Revoir les sessions actives Vaultwarden et forcer changement master password famille (Vaultwarden ne dépend pas d'Authentik pour le master password — c'est sain)

### Scénario 2 — Perte du Mini PC Proxmox (panne matérielle)

1. Acquérir / utiliser un PC de remplacement (peut être moins puissant, temporairement)
2. Réinstaller Proxmox VE 8 (Phase 5)
3. Restaurer les LXCs depuis PBS (Pi5) ou cold backup
4. Vérifier IPs et conf réseau (Ansible reconstruit normalement)
5. Tester chaque service un par un

### Scénario 3 — Incendie / vol total

1. Récupérer le disque cold backup chez le tiers de confiance (parents)
2. Acquérir nouveau matériel (Mini PC, Pi5, N150 si OPNsense aussi parti)
3. Reproduire les phases 0 à 14 avec le repo Git de doc/Ansible (idéalement aussi sauvegardé sur GitHub privé en plus du clone local)
4. Restaurer les datas depuis le disque cold
5. Reconfigurer les comptes famille (réémission TOTP)

### Scénario 4 — OPNsense inaccessible (config foireuse, MAJ ratée, etc.)

1. Brancher un câble Ethernet directement entre laptop et OPNsense P5 (RESCUE)
2. Ton laptop prend une IP DHCP en `192.168.99.0/24`
3. Accès SSH ou HTTPS à `192.168.99.1` (OPNsense)
4. Diagnostic et correction
5. Débrancher le câble, vérifier que P5 reste désactivé en exploitation

### Scénario 5 — Perte du master password Vaultwarden

1. Récupérer la copie papier offline (chez parents)
2. Si la copie papier est perdue ET la mémoire défaillante : **le coffre est définitivement perdu**
3. C'est par construction. Tu auras à recréer un nouveau coffre vierge

> **Leçon** : la copie papier offline n'est pas optionnelle. Faite jour 1, vérifiée annuellement (lecture à voix haute + remise sous enveloppe scellée).

### Scénario 6 — Perte ou vol d'un device avec profil WG-ADMIN-RELAY

> Spécificité : avec l'architecture relay, les peers sont déclarés **sur le hub VPS**, pas sur OPNsense. La révocation se fait donc côté VPS.

1. Accès SSH au VPS Hetzner depuis un autre device WG-ADMIN-RELAY encore valide (ou directement depuis la console Hetzner si tous les devices sont perdus)
2. Éditer `/etc/wireguard/wg-admin.conf` sur le VPS : commenter ou supprimer le bloc `[Peer]` correspondant au device compromis
3. `wg syncconf wg-admin <(wg-quick strip wg-admin)` pour appliquer sans interruption des autres peers
4. Vérifier : `wg show wg-admin` ne liste plus le peer révoqué
5. Générer une nouvelle paire de clés pour le device de remplacement, ajouter un nouveau peer dans `/etc/wireguard/wg-admin.conf` sur le VPS, distribuer le profil au nouveau device
6. Re-sync : `wg syncconf wg-admin <(wg-quick strip wg-admin)`
7. Documenter dans le repo (sans clé en clair) : date, device perdu, peer révoqué, device de remplacement

> **Pré-requis** : runbook `wg-revoke-peer.md` à créer dans `docs/runbooks/` avec la procédure complète et les commandes exactes.

### Scénario 7 — Panne VPS Hetzner (admin distant temporairement perdue)

> **Symptôme** : depuis 4G, le tunnel WG-ADMIN-RELAY ne monte plus, le portfolio `portfolio.ldesfontaine.com` retourne une erreur de connexion, les services privés (vault, files) sont inaccessibles depuis l'extérieur.

**Diagnostic préalable**
1. Vérifier la dispo du VPS depuis 4G : `ping <vps_pub_ip>`, ou statut Hetzner (status.hetzner.com)
2. Si VPS down côté Hetzner : maintenance planifiée ou panne réelle → attendre la résolution
3. Si VPS up mais services down : SSH au VPS, vérifier état services (`systemctl status wg-quick@wg-admin docker`)

**Cas A — Panne courte (< quelques heures), tu es chez toi**
1. Aucune action urgente. Le réseau interne fonctionne, la famille n'est pas impactée.
2. L'admin local reste OK via le réseau MGMT (laptop branché en VLAN 10 via switch ou en LAN par défaut).
3. Attendre la résolution Hetzner.

**Cas B — Panne courte, tu es en déplacement**
1. Si la panne est annoncée < 1h : patienter.
2. Si tu as un besoin urgent d'admin : aucun moyen tant que VPS down. **C'est le trade-off assumé du choix architectural.**
3. Si urgence absolue : appeler quelqu'un sur place pour brancher RESCUE physique et opérer en local (voir cas C).

**Cas C — Tu es sur place avec accès physique (RESCUE)**
1. Brancher câble ethernet sur port P5 OPNsense (port RESCUE)
2. Configurer ton laptop en IP statique `192.168.99.10/24` (réseau RESCUE)
3. Accès SSH à OPNsense via `192.168.99.1`
4. Tu as l'admin complet localement, indépendamment de tout tunnel
5. Une fois terminé : débrancher RESCUE, OPNsense bascule en mode normal

**Cas D — Panne longue (> 24h) ou crash dur du VPS**
1. Provisionner un nouveau VPS Hetzner via Ansible (ou autre provider en cold standby si configuré)
2. Run `ansible-playbook deploy-vps.yml` qui pose : Pangolin + CrowdSec + nginx portfolio + WG hub admin
3. Distribuer la nouvelle clé publique VPS et le nouvel endpoint aux clients (laptop, phone, OPNsense)
4. Renseigner la nouvelle clé/endpoint sur OPNsense via Ansible
5. Mettre à jour les records DNS Cloudflare (A + AAAA) pour pointer vers le nouveau VPS
6. Le tunnel WG-PUB (Newt) se reconnecte automatiquement après mise à jour de sa conf
7. Validation : services publics accessibles, admin distant remarche

> **Temps de reconstruction VPS** : ~30 minutes si tout est en Ansible, ~2h si tu refais à la main. **C'est pour ça que tout doit être en IaC**.

> **Note** : pendant la panne, les services publics (portfolio, vault, etc.) sont également down côté Internet. Mais ils restent **accessibles depuis le réseau interne** via Traefik interne et split-horizon DNS (cf. concept 14.5). Ta famille peut continuer à utiliser Vaultwarden chez elle.

---

## 14. Concepts critiques

### 14.1 Le piège de "any" et l'alias PRIVATE_NETS

OPNsense **route entre les VLANs**. Quand tu écris une règle firewall avec `destination = any`, tu autorises littéralement **n'importe quelle IP**, **y compris les autres VLANs internes**.

Exemple naïf qui casse la segmentation :

```
ALLOW LAN → any (any port)
```

Tu penses "OK mes utilisateurs LAN peuvent surfer". Sauf que `any` inclut :

- Internet (oui)
- 10.10.10.0/24 (MGMT) — paf, ils peuvent attaquer Proxmox
- 10.10.60.0/24 (SVC_PRIV) — paf, ils peuvent attaquer Authentik
- 10.10.99.0/24 (BACKUP) — paf, ils peuvent atteindre PBS

Pourquoi ? Parce qu'OPNsense **route** entre tes VLANs (c'est son boulot). La règle dit "OK pour atteindre n'importe quelle IP", et OPNsense connaît la route vers les autres VLANs. Donc il route. Toute ta segmentation tombe.

**La parade** — un alias `PRIVATE_NETS` qui regroupe **tout ce qui est privé**, dans les deux familles d'IPs (v4 et v6) :

- v4 — RFC 1918 :
  - `10.0.0.0/8`
  - `172.16.0.0/12`
  - `192.168.0.0/16`
- v6 — adresses privées :
  - `fc00::/7` (Unique Local Addresses, RFC 4193 — l'équivalent IPv6 de RFC 1918)
  - `fe80::/10` (link-local, communications locales au lien)

Internet (par construction) n'est dans **aucune** de ces plages. Cet alias unifié couvre les deux stacks dans une seule règle.

Règle correcte :

```
ALLOW LAN → !PRIVATE_NETS (any port)
```

`!PRIVATE_NETS` veut dire "PAS dans cet alias". Donc Internet OK (v4 et v6 le jour où il marche), autres VLANs bloqués.

**Convention** : à chaque fois que tu écris "vers Internet" dans une règle, écris `!PRIVATE_NETS`. Jamais `any`. Et tu n'as pas à dupliquer tes règles le jour où IPv6 deviendra effectivement routable chez toi : l'alias gère déjà les deux familles.

### 14.2 LiveBox 100% fermée : pourquoi et conséquences

#### Le choix architectural

Dans cette archi, la **LiveBox ne forwarde aucun port vers Internet**. Pas de port forward UDP/TCP, pas de DMZ Host, pas d'UPnP. Elle est traitée comme un simple modem fibre opérateur, dont la seule fonction côté entrée est de **drop tout le trafic non sollicité**.

Toute l'exposition publique de l'écosystème (services publics et admin externe) est déportée **côté VPS Hetzner**, qui est de toute façon sur Internet par nature. La maison initie deux tunnels **sortants** vers ce VPS :

- **WG-PUB** : Newt LXC → VPS (services publics — portfolio, vault, files)
- **WG-ADMIN-RELAY** : OPNsense → VPS (admin externe)

#### Conséquences pour un attaquant Internet

Quand un attaquant scanne l'IP publique de la LiveBox :

- **Tous les ports** : LiveBox dropt immédiatement. OPNsense ne voit même pas ces paquets.
- **Aucune réponse à aucun scan**. Du point de vue du scanner, l'IP est "vivante" (elle reçoit ses paquets sortants depuis le NAT côté maison) mais "silencieuse" en entrant. Indistinguable d'une IP qui n'héberge aucun service.

Conséquence : **ton IP publique maison n'apparaît dans aucune liste exploitable de Shodan/Censys/Onyphe**. Tu n'es pas dans les cibles de scans organisés.

#### L'admin LiveBox

L'admin web LiveBox écoute uniquement sur son interface LAN (192.168.1.1, IP privée RFC 1918, non routable depuis Internet). L'option **"administration à distance"** est désactivée (Phase 1). Donc même côté Orange, personne ne peut atteindre l'admin LiveBox depuis Internet via un autre moyen.

#### Depuis le LAN interne (compromis)

La règle `DENY LAN → 192.168.1.1` reste en place. Un PC infecté sur ton LAN qui voudrait pivoter vers la LiveBox sera bloqué par OPNsense, qui filtre les paquets avant de les router.

#### Le canal Orange (TR-069 / CWMP) — risque résiduel

La LiveBox dispose d'un **canal de gestion opérateur** (TR-069 / CWMP) que **tu ne peux pas désactiver** sur une LiveBox grand public. Ce canal permet à Orange de :

- Pousser des MAJ firmware
- Faire du diagnostic à distance
- Reconfigurer la box en cas d'intervention support

C'est le prix de la box opérateur. Si l'infrastructure CWMP d'Orange est compromise, ta LiveBox aussi. **Mitigation** : OPNsense est un cordon sanitaire. La LiveBox est traitée comme un device WAN potentiellement hostile.

> **Note philosophique** : c'est aussi pour ça qu'à terme certains passent en PPPoE direct (+ 802.1X selon région) pour virer la LiveBox totalement. Gris côté CGV Orange et chiant à mettre en place — sage de garder pour plus tard.

### 14.3 Pourquoi tout est sortant (WG-PUB et WG-ADMIN-RELAY)

Les deux tunnels critiques de l'archi suivent le même pattern : **initiés depuis la maison vers le VPS**, jamais l'inverse.

#### WG-PUB (Newt → VPS, services publics)

Newt initie la connexion vers le VPS Pangolin. Aucun port forward n'est nécessaire **vers** la maison pour que les visiteurs accèdent aux services privés. Conséquences :

- La LiveBox reste totalement fermée
- Une compromission VPS n'expose pas la maison directement, mais peut **abuser du tunnel** pour faire des requêtes vers Newt
- D'où la matrice EXPOSED ultra-restrictive : Newt ne peut sortir que vers le VPS sur UDP/51820 et HTTPS pour les updates, pas vers Internet général. Si VPS compromis, Newt est dans une cage.

#### WG-ADMIN-RELAY (OPNsense → VPS, admin externe)

OPNsense initie une connexion sortante vers le hub WG sur le VPS (UDP/51821). Le laptop admin initie aussi une connexion sortante vers ce même hub. Le VPS forwarde le trafic entre les deux peers (`net.ipv4.ip_forward=1`).

Conséquences :

- La LiveBox reste totalement fermée (cohérent avec WG-PUB)
- OPNsense ne fait **aucune** écoute UDP entrante côté WAN
- Une compromission VPS donne à l'attaquant la visibilité sur le canal d'admin (paquets chiffrés bout-à-bout WG entre laptop et OPNsense, donc l'attaquant voit "un tunnel existe" mais pas son contenu)
- D'où l'importance du hardening VPS (CrowdSec, UFW, fail2ban SSH, mises à jour sécu auto)

#### Le SPOF assumé

Le revers de la médaille : si le VPS est down, **l'admin distant est temporairement inaccessible**. C'est un compromis architectural assumé (cf. section 13 scénario 7 pour la procédure de gestion). Mitigations :

- Port RESCUE physique sur OPNsense P5 reste toujours disponible quand on est sur place
- Hetzner SLA 99,9% (~8h max de panne par an, en pratique nettement moins)
- Reconstruction VPS via Ansible en ~30 min documentée en scénario 7

### 14.4 Master password Vaultwarden ≠ password OIDC

Le master password Vaultwarden dérive **localement** la clé de chiffrement du coffre. C'est de la cryptographie côté client. Ni Authentik, ni Vaultwarden côté serveur, ni Anthropic, ni qui que ce soit ne peut déchiffrer ton coffre sans le master password.

L'OIDC via Authentik authentifie l'**utilisateur** (qui es-tu ?) mais ne peut **PAS** déverrouiller le coffre. C'est sain — ça veut dire qu'une compromission Authentik ne donne pas accès aux mots de passe stockés.

**Conséquence pratique** : la perte du master password = perte définitive du coffre. D'où la copie papier offline.

### 14.5 Split-horizon DNS

Unbound sur OPNsense résout `vault.ldesfontaine.com` différemment selon qui demande :

- **Depuis l'intérieur** (LAN, etc.) → IP interne (Traefik interne dans SVC_PRIV)
- **Depuis l'extérieur** (Internet) → IP du VPS (résolu par Cloudflare)

Avantages :

- Performance interne (pas de loop par le VPS)
- Cert wildcard valide partout (même nom DNS)
- Cohérence des URLs (un seul nom à retenir)

Inconvénient :

- Requiert configuration manuelle des overrides Unbound à chaque nouveau service
- À automatiser via Ansible une fois la base posée

### 14.6 Pourquoi Authentik en single-instance et pas HA

Pour un homelab familial (5-10 utilisateurs), Authentik en HA est :

- Surdimensionné (overhead opérationnel)
- Source de complexité (réplication PostgreSQL, gestion des secrets multi-instance, élections de leader)
- Inutile statistiquement (un LXC bien backupé tombe 0,5h/an max)

La parade au single point of failure est **un backup quotidien PBS + DR documentée**. En cas de panne Authentik, le service public est down 30 minutes le temps de restore, et c'est acceptable pour ce contexte.

### 14.7 NTP et OIDC : pourquoi l'horloge UTC est non négociable

Les tokens OIDC échangés entre Authentik (IDP) et Vaultwarden / Filebrowser-Quantum (clients) contiennent trois timestamps **en UTC** :

- `iat` (issued at) — moment d'émission du token
- `nbf` (not before) — token pas valide avant cet instant
- `exp` (expires) — token pas valide après cet instant

Le client OIDC vérifie ces timestamps avec **sa propre horloge UTC**. Si l'écart dépasse la tolérance (typiquement 30 à 60 secondes selon implémentation), le token est rejeté avec `invalid_token`. Symptôme côté utilisateur : login en boucle inexpliqué, sans message clair.

#### Important : timezone ≠ horloge

- L'**horloge système** d'une machine est un compteur en secondes depuis le 1er janvier 1970 UTC (Unix epoch). C'est une valeur **absolue, universelle**, identique partout sur Terre à un instant T donné.
- La **timezone** (`Europe/Paris`, `UTC`, `America/New_York`, etc.) est **uniquement une couche d'affichage** par-dessus cette horloge absolue. Elle change la manière dont `date` ou les logs affichent l'heure, mais **pas la valeur sous-jacente**.

Conséquence : un VPS Hetzner en Allemagne et un LXC Authentik en France, **synchronisés via NTP**, ont **exactement la même horloge UTC** à la milliseconde près, indépendamment de leur timezone d'affichage. Le pays où tourne la machine n'a aucun impact sur la validité des tokens OIDC.

#### Ce qui casse vraiment

- VM ou LXC sans client NTP actif → dérive progressive (jusqu'à plusieurs minutes par mois)
- Pi5 qui boote sans connexion réseau initiale → prend l'heure RTC qui peut être fausse de plusieurs minutes
- VM après suspend/snapshot/migration → décalage immédiat
- Service NTP cassé silencieusement (ex. firewall qui bloque UDP/123 sans qu'on le voie)

#### Mitigation

- `chrony` (ou `systemd-timesyncd`) activé via le rôle Ansible `common`, sur **tous** les hôtes : Proxmox, tous les LXCs, le VPS Hetzner, le Pi5 PBS
- Source NTP : pool public (`pool.ntp.org`) ou `time.cloudflare.com`
- UDP/123 explicitement autorisé en sortie dans toutes les règles firewall (déjà prévu pour BACKUP, à vérifier sur les autres VLANs)
- Recommandation : **timezone UTC partout sur les serveurs** pour faciliter la lecture cross-machines des logs ; timezone locale uniquement sur le laptop d'admin
- Vérification mensuelle : `chronyc tracking` sur les hôtes critiques (Authentik, Vaultwarden, VPS)

### 14.8 Où se termine le tunnel Pangolin/Newt côté maison

Le tunnel WG-PUB qui relie le VPS (Pangolin) au réseau interne **n'est PAS terminé sur OPNsense, ni sur chaque LXC/VM individuel**. Il est terminé sur **un seul point** : le LXC Newt situé dans le VLAN EXPOSED (10.10.50.0/24).

#### Architecture du flux d'une requête publique

```
Visiteur Internet
   │
   ▼ HTTPS (v4 ou v6)
DNS Cloudflare → IP du VPS Hetzner
   │
   ▼ TCP/443
Pangolin sur VPS (Traefik intégré + serveur WireGuard)
   │
   ▼ via tunnel WG-PUB (UDP/51820 sortant initié depuis Newt)
LXC Newt — VLAN 50 EXPOSED (10.10.50.X)
   │
   ▼ TCP/443 (HTTP intra-réseau)
LXC Traefik interne — VLAN 60 SVC_PRIV (10.10.60.X)
   │
   ▼ routing par hostname
LXC Vaultwarden / Filebrowser / Authentik — VLAN 60 SVC_PRIV
```

#### Pourquoi pas sur OPNsense

OPNsense est basé sur FreeBSD et conçu pour faire du **routage et firewall**, pas pour héberger un agent applicatif comme Newt :

- Coupler la fonction firewall et la fonction tunnel applicatif casse la séparation des responsabilités
- Une compromission de Newt donnerait directement un foothold sur le firewall — catastrophique
- La mise à jour, le backup et la reproduction en IaC sont plus difficiles

#### Pourquoi pas un Newt par service

Pangolin est conçu pour fonctionner avec **un Newt par "site"** (= une localisation physique du réseau privé). Multiplier les Newt voudrait dire :

- N tokens à gérer au lieu d'un
- N tunnels WireGuard sortants à maintenir
- Multiplication de la surface d'attaque pour zéro bénéfice

#### Pourquoi le LXC dédié dans EXPOSED est le bon endroit

- **Point de contact unique avec le VPS** (qui peut un jour être compromis), donc on l'isole dans une cage stricte (matrice firewall section 9 : Newt ne peut sortir que vers `VPS_PANGOLIN` sur UDP/51820, et joindre `SVC_PRIV` sur TCP/443 — rien d'autre)
- **Blast radius contenu** : si Newt est compromis (CVE Pangolin par exemple), l'attaquant ne peut atteindre ni MGMT, ni BACKUP, ni le LAN, ni Internet général
- **Reconstruction triviale via Ansible** : Debian 13 minimal + Docker + container Newt avec token. Un rôle Ansible `newt` suffit. Le LXC est jetable.

### 14.9 Choix WG-ADMIN-RELAY vs autres approches d'admin externe

#### L'arbre de décision

Pour gérer l'admin externe d'un homelab depuis Internet, plusieurs approches existent. Voici comment cette archi a tranché :

```
Question initiale : comment accéder à l'admin depuis l'extérieur ?
│
├── Option 1 : Port forward UDP/51820 direct LiveBox → OPNsense
│   ├── ✅ Simple, zéro dépendance tierce
│   ├── ✅ Indépendant du VPS
│   ├── ❌ IP maison visible Shodan (UDP/51820 marqué open|filtered)
│   ├── ❌ Pas compatible CGNAT
│   └── ❌ Cohérence cassée : les services publics passent par VPS
│      sortant, l'admin par port ouvert → deux patterns
│
├── Option 2 : Tailscale/Netbird sur OPNsense
│   ├── ✅ Zéro port ouvert, zéro visibilité Shodan
│   ├── ✅ NAT traversal automatique (CGNAT-compatible)
│   ├── ❌ Dépendance plan de contrôle Tailscale.com
│   ├── ❌ OAuth tiers requis pour l'auth (Google/Microsoft/GitHub)
│   └── ❌ Self-host Headscale = retour SPOF (où l'héberger ?)
│
├── Option 3 : VPS-relay via LXC dans Proxmox
│   ├── ✅ Zéro port ouvert
│   ├── ❌ Dépendance Proxmox (si Proxmox down, admin inaccessible)
│   ├── ❌ Termine sur LXC, pas sur OPNsense bare-metal
│   └── ❌ Mauvais pour le scénario "Proxmox crash, je dois admin OPNsense"
│
└── Option 4 (CHOISIE) : VPS-relay avec OPNsense en client sortant
    ├── ✅ Zéro port ouvert sur LiveBox
    ├── ✅ Zéro visibilité Shodan côté maison
    ├── ✅ Cohérence parfaite avec WG-PUB (même pattern : sortant)
    ├── ✅ Termine sur OPNsense bare-metal (indépendant Proxmox)
    ├── ✅ Zéro dépendance SaaS tiers
    ├── ⚠️ Dépendance VPS (assumée — voir mitigations)
    └── ⚠️ Latence admin +30-50 ms (négligeable)
```

#### Pourquoi pas Option 1 (port forward direct)

Considéré et envisagé en v1.6 du doc. Cassé en v1.7 pour les raisons suivantes :

- **IP maison visible Shodan** — cosmétique mais constant
- **Cohérence cassée** : les services publics passent par tunnel sortant (VPS), pourquoi pas l'admin ? Faire pareil partout = doc plus simple à raisonner
- **Pas compatible CGNAT** futur (déménagement, changement de FAI éventuel)

Le seul avantage net (indépendance VPS) est mitigé par le port RESCUE physique côté maison.

#### Pourquoi pas Option 2 (Tailscale)

Tailscale est techniquement excellent. Refusé pour deux raisons :

- **Dépendance au plan de contrôle Tailscale.com** — c'est un SaaS tiers, même si le client est open-source. Ton accès admin dépend de leur uptime, leur politique, leur survie économique.
- **Auth via OAuth tiers** (Google/Microsoft/GitHub) — encore un autre fournisseur dans la chaîne.

Headscale (équivalent open-source self-hosted du plan de contrôle Tailscale) résoudrait le SaaS, mais doit être hébergé quelque part. Sur ton VPS = retour à la case "dépendance VPS", sans gagner les avantages d'Option 4. Sur un autre cloud = nouvelle dépendance.

#### Pourquoi pas Option 3 (VPS-relay via LXC)

Considéré au cours du raisonnement, refusé car ça ajoute **Proxmox comme dépendance** pour l'admin externe. Si Proxmox crash (kernel panic, disque mort), le LXC relay est down → admin distant inaccessible. Inacceptable étant donné que l'admin externe doit pouvoir **diagnostiquer** un crash Proxmox.

#### Pourquoi Option 4 a été retenue

- **Cohérence architecturale** : tous les flux entrants depuis Internet (services publics ET admin) passent par le VPS. La maison n'expose rien.
- **Termination sur OPNsense bare-metal** : indépendant de Proxmox, donc l'admin externe fonctionne même si Proxmox est complètement HS.
- **Zéro dépendance tierce** : pas de Tailscale.com, pas d'OAuth Google/Microsoft, juste OPNsense + WireGuard pur + VPS Hetzner que tu contrôles.
- **SPOF VPS assumé** : Hetzner SLA 99,9%, port RESCUE physique en fallback ultime, reconstruction VPS Ansible en 30 min documentée (scénario 7 section 13).

#### Quand reconsidérer ?

À évaluer si :

- Tu veux ajouter plusieurs admins distincts avec ACLs identity-based fines → Tailscale Enterprise ou Headscale + Authentik OIDC
- Tu déménages dans une zone CGNAT et perds ton IP publique routable → impact zéro car déjà compatible CGNAT par design (sortant depuis maison)
- Hetzner a des problèmes récurrents → migrer vers un autre provider VPS, ou multi-providers

Mais en 2026 avec ton infra actuelle, Option 4 est l'optimum.

---

## 15. Pièges identifiés à éviter

| Piège | Explication | Mitigation |
|---|---|---|
| Règle firewall trop permissive `any` | Casse la segmentation VLAN sans qu'on s'en rende compte | TOUJOURS utiliser `!PRIVATE_NETS` au lieu de `any` quand on veut dire Internet (cf. concept 14.1) |
| LiveBox reboot Orange forcé | Orange peut forcer un reboot LiveBox la nuit pour MAJ firmware. Services down 2-3 min. | Acceptable, monitorer durée + fréquence. Notif si persistant. |
| Canal CWMP / TR-069 Orange | Tu ne peux pas désactiver la gestion à distance par Orange sur LiveBox grand public. | Traiter LiveBox comme device WAN potentiellement hostile. OPNsense fait barrage. |
| Perte IPv6 côté maison | OPNsense ne reçoit pas un préfixe IPv6 propre derrière la LiveBox (double-NAT v4 imposé par absence de mode bridge sur LiveBox 6, et délégation v6 défaillante). Internet sortant maison reste IPv4 only. | Acceptable. Stratégie dual-stack tout de même : alias `PRIVATE_NETS` couvre v4+v6, support v6 OPNsense activé. Le jour du passage en PPPoE direct ou évolution Orange, IPv6 partira tout seul sans réécriture des règles. VPS Hetzner déjà dual-stack natif (records AAAA actifs). |
| Master password Vaultwarden oublié | Perte définitive du coffre (chiffrement côté client) | Copie papier offline chez tiers de confiance + tête. Vérification annuelle. |
| Clé PBS perdue | Backups inutilisables | Copie papier offline + Vaultwarden |
| Backup non testé | Découverte qu'il est corrompu le jour où on en a besoin | Test restore trimestriel obligatoire, consigné dans la doc |
| Pangolin = OIDC provider ? | Pangolin est OIDC **client** uniquement (consume Authentik). Ne pas s'en servir comme IDP. | Authentik est l'IDP. Pangolin est un gate qui délègue à Authentik. |
| Cert wildcard en clair sur disque | Risque exfiltration | Permissions strictes (mode 600), volumes chiffrés sur supports persistants |
| LXC privilégié | Bypass des limites kernel — escalade plus facile | Toujours créer en LXC unprivileged (option par défaut Proxmox) |
| Proxmox UI exposé | Surface d'attaque énorme, CVEs régulières | Accessible UNIQUEMENT via WG-ADMIN-RELAY, jamais public. Firewall MGMT bloque le LAN. |
| Authentik branché à Proxmox pour l'admin | Dépendance circulaire (si Authentik HS, plus d'admin Proxmox) | Proxmox reste en auth locale (login + TOTP Proxmox) |
| Single instance Authentik | Si compromise ou perdue, tout est down | Backups quotidiens vers PBS + DR documentée + test annuel |
| Authentik = SPOF pour Vaultwarden ? | Si Authentik down, plus de SSO Vaultwarden | Vaultwarden conserve auth locale en parallèle. Tu peux toujours te connecter avec login + master password Vaultwarden, sans OIDC. À configurer en phase 11. |
| Newt compromis exfiltre via tunnel WG-PUB | VPS attaque Newt → Newt attaque le réseau interne | Cage stricte EXPOSED (section 9). Newt ne peut joindre que SVC_PRIV via Traefik :443. |
| Cloudflare proxy activé par mégarde | Cloudflare peut MITM tes services privés (terminaison TLS chez eux) | Vérifier mensuellement que les records sont en "DNS only" (orange cloud OFF) |
| Repo Git public par erreur | Exfiltration des configs Ansible (même sans secrets, structure révèle l'archi) | Repo en visibilité **privée** dès la création. Vérifier les permissions. |
| Token API Cloudflare en clair | Token avec scope DNS Edit = défacement DNS possible | Stocker uniquement en Ansible vault chiffré, jamais en clair. Rotation annuelle. |
| Câble RESCUE branché en permanence | Quelqu'un trouve le câble, contourne tout le firewall | Câble RESCUE physiquement débranché en exploitation, rangé. Brancher uniquement en cas d'urgence. |
| Pas de bastion intermédiaire pour Ansible | `ansible-playbook` depuis ton laptop direct vers les hôtes via WG | Acceptable pour solo-admin. À reconsidérer si tu ouvres l'admin à un copain plus tard. |
| Backup chiffré sans tester la clé | Tu apprends que la clé est mauvaise au moment du restore | Premier restore test PBS dès la phase 13, **avant** d'avoir des données de valeur dedans |
| Désynchronisation NTP entre Authentik et clients OIDC | OIDC casse silencieusement avec dérive > 30s — login en boucle inexpliqué (cf. concept 14.7) | `chrony` partout via rôle Ansible `common`, vérification `chronyc tracking` mensuelle sur Authentik, Vaultwarden, VPS |
| Rate limit Let's Encrypt (50 certs / semaine / domaine) | Test ACME en boucle ou config foireuse qui retente sans cesse → ban 7 jours | Backup `acme.json` (cf. section 10) restauré pour reprise après réinstall ; ne jamais toucher au resolver ACME en prod sans avoir validé ailleurs ; en cas de refonte majeure de la chaîne ACME, basculer temporairement sur le serveur de staging LE le temps de valider |
| VPS Hetzner = SPOF pour l'admin externe | Panne VPS → tunnel WG-ADMIN-RELAY down → admin distant inaccessible | Procédure RESCUE physique (port P5 OPNsense) **imprimée et accessible hors infra** (papier, dans le coffre où est le master Vaultwarden). Procédure reconstruction VPS via Ansible documentée (scénario 7 section 13). |
| Procédure RESCUE oubliée ou non testée | Le jour où le VPS est down ET tu es chez toi, tu ne sais pas comment brancher RESCUE | Test RESCUE physique à inclure dans la validation Phase 1 : brancher câble P5, configurer laptop en 192.168.99.10/24, vérifier SSH vers 192.168.99.1. Tester au moins une fois par an. |
| Clé privée WireGuard VPS oubliée dans Ansible vault | Régénération impossible sans casser tous les peers | Backup chiffré quotidien de `/etc/wireguard/` du VPS dans PBS (via Ansible). En cas de perte, restore PBS. |

---

## 16. Procédures de mise à jour

### 16.1 Philosophie : 3 cadences selon le risque

Tu n'updates pas tout de la même façon. Hiérarchie qui marche en homelab :

| Cadence | Quoi | Risque | Quand |
|---|---|---|---|
| **Sécurité urgente** | Patch CVE sur composant exposé Internet (Pangolin, CrowdSec, kernel VPS) | Faible (patch ciblé) | Dans les 24-48h après publication |
| **Routine** | `apt upgrade` Debian sur LXCs, VMs, VPS, Pi5 (via Ansible) | Faible | Hebdomadaire — fenêtre fixe (samedi matin par exemple) |
| **Versions majeures** | OPNsense 25.x → 26.x, Proxmox 8 → 9, Authentik major release, Pangolin major | Élevé (breaking changes) | Trimestrielle, après lecture release notes + snapshot |

### 16.2 Auto-updates : SÉCURITÉ UNIQUEMENT, jamais de versions majeures

> **Principe non négociable** : les mises à jour automatiques sont **strictement limitées aux patchs de sécurité Debian** (origine `Debian-Security`). Aucune mise à jour majeure, aucune migration cross-release, aucun reboot automatique. Le but : si tu pars trois semaines en vacances, l'infra applique les patchs CVE Debian sans rien casser ; les versions majeures attendent ton retour.

#### Configuration `unattended-upgrades` — appliquée via le rôle Ansible `common` sur tous les hôtes Debian

```bash
# /etc/apt/apt.conf.d/50unattended-upgrades

Unattended-Upgrade::Allowed-Origins {
    # SEULEMENT les patches de sécurité Debian
    "${distro_id}:${distro_codename}-security";

    // PAS "${distro_id}:${distro_codename}-updates" — ça inclurait les point releases
    // PAS "${distro_id}:${distro_codename}-backports" — versions trop fraîches
};

# PAS de reboot automatique : si un kernel security patch est appliqué,
# le binaire est en place mais le reboot reste manuel — toi seul décides quand
Unattended-Upgrade::Automatic-Reboot "false";

# Refuser explicitement les downgrades et les pré-releases
Unattended-Upgrade::Allow-downgrade "false";
Unattended-Upgrade::DevRelease "false";

# Logs détaillés pour audit
Unattended-Upgrade::Verbose "true";
```

#### Ce qui PASSE en auto

- ✅ CVE OpenSSL, sudo, kernel, systemd, OpenSSH, etc. (origine `Debian-Security`)
- ✅ Sur tous les hôtes Debian : LXCs, VMs, VPS, Pi5

#### Ce qui ne passe JAMAIS en auto (manuel obligatoire)

- ❌ Migration cross-release Debian (13 → 14)
- ❌ Backports
- ❌ Reboot après kernel update (le binaire est en place, le reboot = ton choix)
- ❌ **Containers Docker** (Pangolin, Authentik, Vaultwarden, Newt, CrowdSec, Filebrowser) — manuel
- ❌ **OPNsense** firmware ou plugins
- ❌ **Proxmox VE host**
- ❌ **UniFi controller** et firmware AP
- ❌ **Switch** firmware

> **Pas de Watchtower ni d'auto-pull Docker.** Mêmes raisons : un breaking change Pangolin ou Authentik la nuit pendant tes vacances et le service public est cassé. **Manuel uniquement** sur tous les containers applicatifs.

#### Vérification mensuelle

```bash
# Sur n'importe quel host Debian
unattended-upgrade --dry-run --debug 2>&1 | head -40
# Confirme ce qui serait pris en auto au prochain cycle
```

### 16.3 Ordre de mise à jour manuelle : du moins au plus critique

Règle : tu commences par ce qui peut casser sans impacter la famille, tu finis par ce qui casse tout si ça merde.

```
1. VPS Hetzner          → si planté, le portfolio est down. Acceptable.
2. Pi5 PBS              → si planté, plus de backups le temps du fix. Pas urgent.
3. LXCs LAB             → bac à sable, on s'en fout.
4. LXCs SVC_PRIV
   sauf Authentik       → Vaultwarden, Filebrowser : downtime acceptable.
5. Proxmox host         → reboot complet, prévenir famille avant.
6. OPNsense             → si planté, plus de réseau du tout. Snapshot config.xml AVANT.
7. Authentik            → SI planté, plus de SSO. À faire EN DERNIER, infrastructure stable.
```

> **Avant chaque MAJ majeure** (OPNsense firmware, Proxmox dist-upgrade, Authentik) : snapshot Proxmox du LXC concerné. Une commande, 30 secondes : `pct snapshot 110 pre-upgrade-$(date +%F)`. Rollback en cas de pépin : `pct rollback 110 pre-upgrade-2026-XX-XX`.

### 16.4 Procédures par composant

#### OPNsense (manuel — trimestriel firmware, mensuel plugins)

1. UI → System → Firmware → Updates → "Check for updates"
2. **Backup config.xml manuel** (en plus du backup quotidien automatique du rôle `config-backup`)
3. **Lire les release notes** (forum officiel, surtout pour les majors — il y a parfois des migrations de plugin)
4. Cliquer "Update" — reboot automatique pour les firmware updates
5. Validation : ping interne + Internet sortant + un client WG-ADMIN-RELAY qui se reconnecte sans souci

**Major version (ex. 25.x → 26.x)** : préparer une fenêtre dédiée, plan de rollback prêt (USB d'install à jour à portée de main pour un re-flash en cas de fail dur).

#### Proxmox VE (manuel — mensuel)

```bash
apt update
apt dist-upgrade   # PAS "apt upgrade" — manque les déps modifiées
reboot             # uniquement si kernel updated
```

**Major version (ex. 8 → 9)** : exécuter `pve8to9` en pré-check, suivre la procédure officielle Proxmox, snapshot PBS de tous les LXCs critiques avant.

#### Hôtes Debian (LXCs, VMs, VPS, Pi5) — orchestré via Ansible

Playbook `update.yml` lancé hebdomadairement :

```yaml
# ansible/playbooks/update.yml
- name: Update Debian-based hosts
  hosts: debian_all
  serial: 1                           # un host à la fois pour éviter le big bang
  tasks:
    - apt:
        update_cache: yes
        upgrade: dist
        cache_valid_time: 3600
    - reboot:
        reboot_timeout: 300
      when: ansible_reboot_pending | default(false)
```

Lancement progressif :
```bash
ansible-playbook update.yml --limit=lab        # tester sur LAB d'abord
ansible-playbook update.yml --limit=svc_priv   # puis services privés non Authentik
ansible-playbook update.yml --limit=authentik  # Authentik en dernier
```

#### Containers Docker (Pangolin, CrowdSec, Newt, Authentik, Vaultwarden, Filebrowser)

**Manuel obligatoire**, suivre les release notes upstream :

```bash
cd /opt/pangolin   # ou /opt/authentik selon le cas
docker compose pull
docker compose up -d
docker compose logs -f --tail=50    # vérifier qu'il n'y a pas d'erreur
```

> **Attention spécifique Authentik** : changements de schéma DB fréquents entre majors. Toujours snapshot Proxmox du LXC avant + lecture des release notes.

#### UniFi controller (manuel)

- Update controller : via apt (le LXC suit le repo UniFi officiel) ou via UI controller
- Update firmware AP : via UI controller, "Update available" → cliquer
- À faire dans une fenêtre planifiée (~5 min de coupure WiFi à chaque update AP)

#### Switch Netgear MS305E (manuel — rare)

- Firmware updates rares (1-2× / an)
- UI web → Firmware → upload manuel
- Faire en fenêtre planifiée car bascule réseau possible
- **Backup config switch avant** (cf. section 10)

#### LiveBox

Aucun contrôle : Orange te l'update sans te demander. Si elle reboot, perte Internet 2-3 minutes. Acceptable et hors de ton scope.

### 16.5 S'abonner aux flux pour ne pas louper de CVE

| Composant | Flux à suivre |
|---|---|
| OPNsense | Forum officiel + RSS releases |
| Proxmox | Mailing list `pve-user` |
| Pangolin | GitHub releases (notifs activées) |
| Authentik | GitHub releases |
| Vaultwarden | GitHub releases |
| CrowdSec | Newsletter + GitHub releases |
| CVE Debian | `apt list --upgradable` en check hebdo |

### 16.6 Fenêtre de maintenance recommandée

| Cadence | Quand | Quoi |
|---|---|---|
| Hebdomadaire | Samedi matin 9h-10h | Playbook Ansible `update.yml` (apt upgrade routine) |
| Mensuelle | Premier samedi du mois | Proxmox host + OPNsense plugins + UniFi controller + Docker pulls |
| Trimestrielle | Revue calendrier | Versions majeures, planning si upgrade nécessaire |
| À la demande | Sur CVE critique exposée Internet | Patch dans les 24-48h |

---

## 17. Procédures opérationnelles (incidents, reboots, coupures)

### 17.1 Coupure de courant — ordre de boot naturel

Quand l'AC revient (ou que l'UPS reprend la main) :

```
T+0s     : AC restauré
T+5s     : LiveBox commence à booter         (~2 min jusqu'à Internet OK)
T+5s     : OPNsense N150 boote               (~1-2 min jusqu'à services up)
T+10s    : Switch MS305E boote               (~30s)
T+30s    : AP UniFi boote via PoE            (~45s)
T+10s    : Mini PC Proxmox boote             (~1-2 min jusqu'à GUI up)
T+90s    : Proxmox lance les LXCs/VMs selon ordre défini
T+30s    : Pi5 PBS boote                     (~30s)
                                             ⚠️ MAIS PBS reste DOWN
                                             jusqu'au déchiffrement LUKS
                                             (cf. 17.4 — action manuelle)
```

**En théorie tout repart tout seul. En pratique, une seule action manuelle obligatoire sur le Pi5 (cf. 17.4).**

### 17.2 Réglage BIOS Power Recovery (configuration critique)

Sur le **mini PC Proxmox** ET sur le **CWWK N150 OPNsense**, l'option BIOS s'appelle (selon le constructeur) :

- "AC Power Recovery"
- "Restore on AC Power Loss"
- "After Power Failure"
- "AC Back Function"

| Valeur BIOS | Comportement | Recommandation |
|---|---|---|
| Power Off / Stay Off | Reste éteint après coupure → action manuelle obligatoire | ❌ MAUVAIS |
| **Power On / Always On** | Redémarre toujours quand AC revient | ✅ **À CHOISIR** |
| Last State | Reprend l'état pré-coupure | ⚠️ Acceptable, mais si tu l'avais éteinte volontairement, elle ne redémarrera pas après la coupure |

> **À mettre dans le runbook `bios-config.md`** : noter pour chaque machine bare-metal le réglage BIOS appliqué et les autres options critiques (virtualisation activée, AES-NI activé, secure boot off pour Proxmox, etc.).

### 17.3 Configuration autostart Proxmox avec délais

Le piège : si Proxmox lance les LXCs **avant qu'OPNsense ne soit prêt**, ils n'obtiennent pas leur DHCP et certains services partent en vrille au boot.

**Trois parades, à appliquer en combinaison** :

#### A. IPs statiques dans tous les LXCs (recommandé)

C'est ta philosophie IaC de toute façon. Le LXC s'en fiche que DHCP soit up ou pas.

```yaml
# Rôle Ansible lxc-base
- name: Configure static IP
  copy:
    content: |
      auto eth0
      iface eth0 inet static
        address {{ lxc_ip }}/{{ lxc_prefix }}
        gateway {{ lxc_gateway }}
    dest: /etc/network/interfaces
```

#### B. Ordre + délai dans la config Proxmox

```bash
pct set 110 --onboot 1 --startup order=1,up=30,down=60
# order=1  : démarre en premier
# up=30    : attendre 30s avant de démarrer le suivant
# down=60  : 60s pour s'arrêter proprement à l'extinction
```

**Ordre recommandé** :

| Order | LXC | up= | Justification |
|---|---|---|---|
| 1 | Authentik | 60 | Tout en dépend, démarrer en premier avec marge réseau |
| 2 | Traefik interne | 15 | Doit être prêt avant les services qu'il route |
| 3 | Vaultwarden | 10 | Service applicatif |
| 3 | Filebrowser | 10 | Idem |
| 4 | Newt | 15 | Tunnel — peut démarrer après le reste |
| 5 | UniFi controller | 10 | Pas critique pour les autres |
| 9 | LXCs LAB | 5 | En dernier, peu importe |

#### C. Délai sur le premier LXC pour laisser OPNsense finir

`up=60` sur le LXC d'order=1 : Proxmox attend 60s avant de déclarer le LXC "ready" et donc avant de démarrer le suivant. C'est le tampon de sécurité pour qu'OPNsense ait fini ses initialisations.

### 17.4 Point critique — déchiffrement LUKS du datastore PBS sur Pi5

**C'est la SEULE action manuelle obligatoire** après une coupure de courant ou un reboot du Pi5 :

Le Pi5 boote ✅. Mais les NVMe en ZFS mirror chiffrés LUKS ne se montent **pas tout seuls** (par construction — sinon le chiffrement ne sert à rien : n'importe qui qui vole le Pi5 lirait les backups). PBS au démarrage cherche son datastore, ne le trouve pas, refuse de démarrer le service.

**Procédure manuelle après chaque reboot Pi5** :

```bash
# Connexion via WG-ADMIN-RELAY
ssh root@10.10.99.10

# Déchiffrer les deux NVMe (passphrase à taper, depuis Vaultwarden)
cryptsetup luksOpen /dev/nvme0n1p1 backup-1
cryptsetup luksOpen /dev/nvme1n1p1 backup-2

# Importer le pool ZFS
zpool import backup

# Relancer les services PBS
systemctl start proxmox-backup
systemctl start proxmox-backup-proxy

# Vérifier
systemctl status proxmox-backup-proxy
zfs list
```

> **Recommandation** : un script `/usr/local/sbin/pbs-unlock.sh` qui fait ces étapes en demandant la passphrase une seule fois. À installer via Ansible (rôle `pbs`).

> **⚠️ Attention** : ne stocke **JAMAIS** la passphrase LUKS dans un fichier en clair sur le Pi5 (genre "pour automatiser le boot"). Si tu fais ça, le chiffrement ne sert plus à rien — qui vole le Pi5 a accès aux backups. **La friction de 30 secondes au reboot est volontaire et fait partie du modèle de sécurité.**

> **Chaîne de récupération** : la passphrase LUKS est dans Vaultwarden. Vaultwarden est inaccessible si Authentik est down. Mais tu peux toujours te connecter à Vaultwarden directement (login local + master password connu par cœur, indépendant du SSO) — voir piège *"Authentik = SPOF pour Vaultwarden"* en section 15.

### 17.5 Reconnexions automatiques

Une fois tout up, voici ce qui se reconnecte tout seul (zéro action) :

| Composant | Délai typique |
|---|---|
| Tunnel Newt → VPS Pangolin | ~30s (keepalive Newt + reconnect auto) |
| Clients WG-ADMIN-RELAY | À la première requête sortante (split-tunnel) ou immédiat (full-tunnel) |
| AP UniFi → controller | Auto-réadoption, ~30s |
| Records DNS Cloudflare | DNS public toujours up, pas affecté |
| Certs Let's Encrypt | Valides plusieurs semaines, pas affectés |
| Services SSO chain | Reprennent dès qu'Authentik est joignable |

### 17.6 UPS recommandé (à ajouter à l'inventaire matériel)

Tu as un UPS HAT sur le Pi5 : bien, mais insuffisant pour le reste de l'infra.

**Recommandation** : un UPS **600-1000 VA** (~80-150 €) qui alimente :
- LiveBox
- OPNsense N150
- Switch MS305E (et donc l'AP UniFi par PoE)
- Mini PC Proxmox

#### Bénéfices

- **Coupures courtes (< 10 min)** : invisible pour la famille, rien ne s'arrête
- **Coupures longues** : **shutdown gracieux** via NUT (Network UPS Tools) installé sur Proxmox, qui surveille la charge UPS et déclenche un `pct shutdown` propre de tous les LXCs avant de couper le mini PC
- Protection contre **micro-coupures et surtensions**, qui usent les SSD/NVMe à long terme

#### Configuration NUT (à ajouter en phase post-stabilisation)

- Driver USB pour l'UPS sur Proxmox
- Mode `master` sur Proxmox (le plus gros consommateur), `slave` sur Pi5 si tu y mets aussi un USB de l'UPS
- Trigger : à 20% de charge restante UPS, déclencher `shutdown -h now` sur tous les nodes

### 17.7 Checklist post-coupure

À mettre dans `docs/runbooks/post-power-outage.md`. À imprimer aussi (parce que si Internet est down et ton laptop a du jus, tu n'iras pas chercher la procédure dans le repo Git via Internet).

```
[ ] OPNsense joignable via WG-ADMIN-RELAY ?           → ping 10.10.10.1
[ ] Internet fonctionnel ?                       → curl -I https://1.1.1.1
[ ] Proxmox UI joignable ?                       → https://proxmox.ldesfontaine.com
[ ] Tous les LXCs UP ?                           → pct list | grep -v running   (doit être vide)
[ ] Pi5 PBS : LUKS unlock + service start        → procédure 17.4
[ ] Backups quotidiens reprennent ce soir ?      → vérifier UI PBS J+1
[ ] Tunnel Newt → Pangolin connecté (UI vert) ?  → portfolio.ldesfontaine.com depuis 4G
[ ] Authentik fonctionne (login test) ?          → vault.ldesfontaine.com depuis 4G
[ ] Famille a accès au WiFi UniFi ?              → demander confirmation
```

5 minutes max si tout va bien. Si quelque chose coince, tu sais où chercher (la checklist te pointe vers les sections du doc).

---

## 18. Stack monitoring (Phase 2)

> **Quand** : déployé en phase 16 du plan de mise en œuvre (variable, après stabilisation 2-3 mois). La présente section décrit l'**architecture cible**, pas la procédure d'install pas-à-pas.
>
> **Pourquoi cette section dédiée** : le monitoring touche tous les VLANs et nécessite l'ajout de règles firewall, un tunnel WireGuard supplémentaire pour le VPS, l'intégration OIDC Authentik, et une politique de rétention. Trop transverse pour rester dans une simple liste de livrables Phase 16.

### 18.1 Architecture cible

Un **LXC unique** "monitoring" dans **VLAN MGMT (10.10.10.30)** qui regroupe les composants. Pas d'éclatement Prometheus/Loki/Grafana en LXCs séparés (ils communiquent beaucoup entre eux, l'éclatement multiplie les règles firewall pour zéro bénéfice de sécurité).

```
┌─────────────────────────────────────────────────────────────────┐
│ LXC monitoring  (10.10.10.30, VLAN MGMT)                        │
│   • Prometheus       : métriques (TSDB)                         │
│   • Loki             : logs (alternative légère à ELK)          │
│   • Grafana          : dashboards (auth OIDC Authentik)         │
│   • Alertmanager     : routage + dédoublonnage des alertes      │
│   • ntfy             : notifications push (auto-hébergé)        │
└─────────────────────────────────────────────────────────────────┘
       │ scrape multi-VLAN (firewall : MGMT → exporters)
       ▼
   Tous les LXCs Debian (port 9100), OPNsense, Pi5 PBS,
   services natifs (PBS:8007, CrowdSec:6060, Authentik:9300, etc.)
       │
       │ scrape VPS via tunnel WG-MON dédié
       ▼
   VPS Hetzner (Pangolin/CrowdSec/nginx)
```

### 18.2 Sizing du LXC monitoring

| Ressource | Quantité | Justification |
|---|---|---|
| CPU | 4 cores | Prometheus + Loki I/O bound, pas besoin de plus |
| RAM | 4 Go | Prometheus 1-2 Go, Loki 1-2 Go, le reste services légers |
| Disque | 50 Go | Couvre 30j métriques + 14j logs avec marge |
| OS | Debian 13 minimal | Aligné sur convention LXC du homelab |

**Budget RAM consolidé Proxmox** (32 Go physique disponible) :

| Catégorie | RAM réservée |
|---|---|
| Authentik (Postgres + Redis + Server + Worker) | ~2,5 Go |
| Vaultwarden, Filebrowser, Traefik, Newt | ~1,3 Go |
| UniFi controller | 1,5 Go |
| LXCs LAB (variable) | ~4 Go |
| **Sous-total existant** | **~9 Go** |
| **LXC monitoring (à ajouter)** | **4 Go** |
| **Total** | **~13 Go** |
| **Marge restante** | **~19 Go** ✅ |

Le N150 OPNsense (16 Go RAM) absorbe les plugins exporters pour < 100 Mo, négligeable.

### 18.3 Exporters par source

Beaucoup de composants ont un endpoint Prometheus **natif** : à activer plutôt que poser un exporter externe.

| Source | Type | Comment |
|---|---|---|
| OPNsense | Plugin | `os-node_exporter` + plugin métriques firewall (catalogue OPNsense) |
| Proxmox host | Externe | `prometheus-pve-exporter` — stats VMs/LXCs/ZFS |
| Tous les LXCs Debian | Externe | `node_exporter` posé via rôle Ansible `common`, port 9100 |
| Unbound (LXC DNS phase 3) | Externe | `unbound_exporter` — requêtes DNS, cache hit rate, blocages |
| **Pangolin (VPS)** | **Natif** | Endpoint `/metrics` du Traefik intégré, à activer dans la conf |
| **CrowdSec (VPS)** | **Natif** | Endpoint Prometheus port 6060, activé par défaut |
| Newt (LXC EXPOSED) | Natif si dispo | Vérifier doc Pangolin/Newt à la phase 16 |
| **PBS (Pi5)** | **Natif** | Endpoint Prometheus intégré PBS, port 8007 |
| Vaultwarden | Natif | Activable via env var `ENABLE_PROMETHEUS=true` |
| **Authentik** | **Natif** | Endpoint metrics port 9300 |
| Traefik interne (LXC) | Natif | Activable dans `traefik.yml` (`metrics: prometheus:`) |
| UniFi controller | Externe | `unpoller` (LXC dédié ou container) — lit l'API UniFi |
| Containers Docker (sur VPS) | Externe | `cAdvisor` |

> **Note** : les endpoints **natifs** sont à privilégier car maintenus par les projets eux-mêmes, et ne nécessitent pas de poser un binaire supplémentaire.

### 18.4 Scraping du VPS Hetzner — tunnel WG-MON dédié

Le tunnel WG-PUB existant (Newt → VPS) est dédié au routage HTTP retour des services privés. Il n'est pas pensé pour du scrape Prometheus arbitraire. **Solution propre** : un tunnel WireGuard dédié, **WG-MON**, minimal.

```
LXC monitoring  (10.10.10.30, VLAN MGMT)
    │  Interface wg-mon (10.99.0.1/30)
    │
    ▼ UDP/51821 (port différent de WG-ADMIN-RELAY/WG-PUB pour clarté)
VPS Hetzner
    │  Interface wg-mon (10.99.0.2/30)
    │
    ▼ exporters bind sur l'IP wg-mon UNIQUEMENT (jamais sur l'IP publique)
node_exporter:9100 + Pangolin metrics + CrowdSec metrics
```

#### Avantages

- Aucun port supplémentaire exposé sur le VPS côté Internet (les exporters bindent sur `10.99.0.2` uniquement)
- Trafic monitoring isolé du trafic Newt, pas de risque d'interférence
- Si un jour ajout d'un autre VPS ou site distant : même mécanisme, réutilisable

#### Configuration côté VPS

```ini
# /etc/wireguard/wg-mon.conf
[Interface]
Address = 10.99.0.2/30
ListenPort = 51821
PrivateKey = <clé privée VPS>

[Peer]
# LXC monitoring chez toi
PublicKey = <clé publique LXC monitoring>
AllowedIPs = 10.99.0.1/32
PersistentKeepalive = 25
```

Lancement de `node_exporter` avec `--web.listen-address=10.99.0.2:9100` (bind WG-MON uniquement). Pareil pour les autres exporters du VPS.

#### Configuration côté LXC monitoring

```ini
# /etc/wireguard/wg-mon.conf
[Interface]
Address = 10.99.0.1/30
PrivateKey = <clé privée LXC monitoring>

[Peer]
PublicKey = <clé publique VPS>
Endpoint = <IP publique VPS>:51821
AllowedIPs = 10.99.0.2/32
PersistentKeepalive = 25
```

Et dans `prometheus.yml`, on scrape `10.99.0.2:9100`, etc.

### 18.5 Auth Grafana via OIDC Authentik

Pas de login local Grafana. Provider OIDC déclaré dans Authentik, Grafana s'y appuie :

```ini
# /etc/grafana/grafana.ini
[auth.generic_oauth]
enabled = true
name = Authentik
allow_sign_up = true
client_id = <client_id généré dans Authentik>
client_secret = <client_secret>
scopes = openid profile email
auth_url = https://auth.ldesfontaine.com/application/o/authorize/
token_url = https://auth.ldesfontaine.com/application/o/token/
api_url = https://auth.ldesfontaine.com/application/o/userinfo/
role_attribute_path = contains(groups[*], 'admins') && 'Admin' || 'Viewer'
```

#### Bénéfices

- **Une seule MFA** à passer (chaîne Authentik existante)
- **Révocation centralisée** : désactivation d'un user dans Authentik → perte d'accès Grafana automatique
- Mapping de rôles via groupes Authentik : groupe `admins` → rôle Grafana `Admin`, sinon `Viewer`

> **Attention NTP** : OIDC sensible aux décalages d'horloge. `chrony` doit être actif sur le LXC monitoring comme partout (cf. concept 14.7).

### 18.6 Stockage et rétention

| Source | Rétention | Volume estimé |
|---|---|---|
| Prometheus métriques | 30 jours | ~10-15 Go |
| Loki logs | 14 jours | ~10-20 Go (variable selon verbosité OPNsense) |
| Grafana DB + dashboards provisionnés | n/a | < 500 Mo |

**Configuration Prometheus** :
```yaml
--storage.tsdb.retention.time=30d
--storage.tsdb.retention.size=15GB
```

**Configuration Loki** : retention via `compactor` avec `retention_period: 336h` (14 jours).

### 18.7 Backup

Le LXC monitoring est sauvegardé via PBS quotidien comme tous les autres LXCs (rien à faire de spécial, couvert par la phase 12).

> **Note** : si le LXC est perdu, l'historique métriques/logs antérieur au dernier backup PBS est perdu également. Acceptable — c'est de l'observabilité, pas de la donnée business critique. Les configs (Prometheus, Grafana, Alertmanager, dashboards JSON) sont versionnées dans le repo Git Ansible et reproductibles à l'identique.

### 18.8 Alerting via ntfy auto-hébergé

ntfy déployé **dans le LXC monitoring** (container Docker ou install systemd, < 50 Mo RAM). Auto-héberge un endpoint, ajouté aux receivers Alertmanager :

```yaml
# alertmanager.yml
receivers:
  - name: 'ntfy'
    webhook_configs:
      - url: 'https://ntfy.ldesfontaine.com/alerts'
        send_resolved: true
```

App ntfy installée sur le téléphone admin (via SSID Maison ou en 4G), notifications reçues sans dépendance à Discord/Telegram/Slack.

#### Exposition publique de ntfy

Optionnelle. Si activée → ressource Pangolin avec auth Authentik (comme tes autres services SVC_PRIV). Sinon → accès uniquement via WG-ADMIN-RELAY, notifs reçues seulement quand WG est connecté.

#### Alertes prioritaires à configurer

À déployer en priorité dans `prometheus_rules.yml` :

| Alerte | Trigger | Sévérité |
|---|---|---|
| `HostDown` | `up == 0` pendant 5 min sur un host critique | Critical |
| `DiskFillingUp` | `< 15%` espace libre sur n'importe quel filesystem | Warning |
| `DiskAlmostFull` | `< 5%` espace libre | Critical |
| `MemoryHigh` | `> 90%` RAM utilisée pendant 10 min | Warning |
| `OPNsenseDown` | OPNsense ne répond plus au scrape | Critical |
| `WG_PUB_Down` | Tunnel Newt → VPS down (UI Pangolin) | Critical |
| `BackupNotRunning` | Pas de backup PBS depuis > 36h | Warning |
| `CertExpiring` | Cert TLS expire dans < 14 jours | Warning |
| `CrowdSecBanRateHigh` | > 50 IPs bannies / heure (= attaque en cours) | Warning |
| `AuthentikDown` | Authentik metrics non joignable | Critical |

### 18.9 Règles firewall additionnelles à ajouter en phase 16

À insérer dans la matrice section 9 **lors de la phase 16** (pas avant, sinon trafic non utilisé) :

| Source | Destination | Port | Action | Justification |
|---|---|---|---|---|
| MGMT (10.10.10.30) | tous les LXCs/VMs Debian | tcp/9100 | ALLOW | Scrape `node_exporter` |
| MGMT (10.10.10.30) | OPNsense (10.10.10.1) | tcp/9100, tcp/9090 | ALLOW | Scrape plugins OPNsense |
| MGMT (10.10.10.30) | PBS Pi5 (VLAN BACKUP) | tcp/8007 | ALLOW | Scrape PBS metrics natif |
| MGMT (10.10.10.30) | LXC Authentik (SVC_PRIV) | tcp/9300 | ALLOW | Scrape Authentik metrics |
| MGMT (10.10.10.30) | LXC Vaultwarden (SVC_PRIV) | tcp/443 | ALLOW | Scrape via endpoint metrics |
| MGMT (10.10.10.30) | VPS_PANGOLIN | udp/51821 | ALLOW | Tunnel WG-MON |
| MGMT (10.10.10.30) | !PRIVATE_NETS | tcp/443 | ALLOW | Updates LXC monitoring |
| MGMT (10.10.10.30) | !PRIVATE_NETS | udp/123, udp/53 | ALLOW | NTP, DNS |

> **Note** : aucune règle entrante autorisée vers le LXC monitoring depuis les autres VLANs. Les utilisateurs accèdent à Grafana **uniquement** depuis WG-ADMIN-RELAY, ou via Pangolin si tu décides de l'exposer publiquement avec auth Authentik.

### 18.10 Roadmap de déploiement (sous-phases de Phase 16)

| Sous-phase | Durée | Contenu |
|---|---|---|
| 16.a Fondations | ~½ jour | LXC créé, Prometheus + Grafana minimal, dashboard `1860` (Node Exporter Full), 1-2 LXCs scrapés |
| 16.b Couverture infra | ~1 jour | `prometheus-pve-exporter` + plugins OPNsense + WG-MON vers VPS + tous les exporters natifs activés |
| 16.c Logs (Loki) | ~½ jour | Loki ajouté, Promtail (ou Alloy) sur Proxmox + 2-3 LXCs critiques + syslog OPNsense |
| 16.d Auth + alerting | ~½ jour | OIDC Authentik branché sur Grafana, Alertmanager + ntfy déployés, alertes prioritaires configurées |
| 16.e Dashboards custom | continu | Construction et provisioning Ansible des dashboards pertinents pour ton infra |

---

## Annexes

### A. Conventions de nommage

| Type d'entité | Convention | Exemple |
|---|---|---|
| Hostname LXC | `lxc-<service>-<env>` | `lxc-authentik-prod` |
| Hostname VM | `vm-<service>-<env>` | `vm-windows-lab` |
| Nom DNS interne | `<service>.ldesfontaine.com` | `vault.ldesfontaine.com` |
| Alias OPNsense | UPPERCASE | `PRIVATE_NETS`, `VPS_PANGOLIN` |
| Rôle Ansible | `<service>-<role>` | `proxmox-host`, `lxc-base`, `traefik-internal` |
| Branche Git | `feat/<description>`, `fix/<description>` | `feat/add-grafana` |
| Tag Git | `vX.Y.Z` | `v1.0.0` |

### B. Structure recommandée du repo

```
homelab/
├── docs/
│   ├── cahier-des-charges-homelab.md    # ce fichier
│   ├── runbooks/                         # procédures opérationnelles
│   │   ├── backup-cold-sync.md
│   │   ├── restore-lxc-from-pbs.md
│   │   └── livebox-reboot-recovery.md
│   ├── architecture/
│   │   ├── schema-physique.svg
│   │   └── schema-logique.svg
│   └── decisions/                        # ADR (Architecture Decision Records)
│       ├── 001-pangolin-vs-cloudflare-tunnel.md
│       ├── 002-authentik-single-instance.md
│       └── 003-vps-relay-pour-admin-externe.md
├── ansible/
│   ├── inventory/
│   │   ├── hosts.yml
│   │   └── group_vars/
│   ├── roles/
│   │   ├── common/
│   │   ├── proxmox-host/
│   │   ├── lxc-base/
│   │   ├── opnsense-base/                # via collection ansibleguy
│   │   ├── authentik/
│   │   ├── vaultwarden/
│   │   ├── filebrowser/
│   │   ├── traefik-internal/
│   │   ├── pbs-client/
│   │   └── newt/
│   ├── playbooks/
│   │   ├── site.yml
│   │   ├── deploy-services.yml
│   │   └── disaster-recovery.yml
│   └── vault.yml                         # secrets chiffrés
├── terraform/                            # optionnel — provisioning VPS
│   └── hetzner/
│       ├── main.tf
│       └── variables.tf
└── README.md
```

### C. Liens utiles

- OPNsense — https://opnsense.org
- Proxmox VE — https://www.proxmox.com
- Pangolin (Fossorial) — https://pangolin.fossorial.io
- Authentik — https://goauthentik.io
- Vaultwarden — https://github.com/dani-garcia/vaultwarden
- Filebrowser Quantum — https://github.com/gtsteffaniak/filebrowser
- CrowdSec — https://www.crowdsec.net
- Proxmox Backup Server — https://www.proxmox.com/en/proxmox-backup-server
- Ansible Collection OPNsense (ansibleguy) — https://galaxy.ansible.com/ansibleguy/opn
- StevenBlack hosts — https://github.com/StevenBlack/hosts
- OISD blocklist — https://oisd.nl

### D. Changelog

| Date | Version | Auteur | Changement |
|---|---|---|---|
| (à remplir le jour J) | 1.0 | ldesfontaine | Création initiale du cahier des charges |
| (à remplir le jour J) | 1.1 | ldesfontaine | Ajout NTP/chrony dans la stack et concept critique 14.7 ; backup des configs équipements réseau (OPNsense, switch, UniFi) en section 10 ; scénario DR 6 (révocation peer WG-ADMIN) ; deux nouveaux pièges en section 15 (NTP, rate limit Let's Encrypt) |
| (à remplir le jour J) | 1.7 | ldesfontaine | **Bascule architecturale majeure** : abandon du port forward UDP/51820 sur LiveBox (v1.6) au profit d'un tunnel WireGuard **sortant** OPNsense → hub WG sur VPS Hetzner ("WG-ADMIN-RELAY"). **La LiveBox est désormais totalement fermée** (zéro port forward, zéro DMZ Host, ni maintenant ni jamais). Renommage WG-ADMIN → WG-ADMIN-RELAY partout. Modifs propagées : section 2 inventaire, section 3 ports OPNsense WAN, section 9 matrice firewall (suppression règle entrante UDP/51820, ajout sortante vers VPS, renommage WG-ADMIN-RELAY), section 11 entièrement réécrite (3 tunnels : WG-PUB / WG-ADMIN-RELAY / WG-MON tous sortants, tableau ports VPS exposés), section 12 préambule (LiveBox 100% fermée), bloc C tableau reformulé, Phase 1 (aucun port forward ni maintenant ni jamais), Phase 4 entièrement réécrite (client WG sortant + clés préparées, activation différée bloc C), Phase 5 référence WG-ADMIN-RELAY, Phase 9 enrichie (ajout WG hub sur VPS + UFW UDP/51821), Phase 14.b entièrement réécrite (plus de port forward, activation tunnel relay), Phase 14.d note finale (LiveBox = simple modem). Nouveau scénario DR 7 (panne VPS — cas A/B/C/D dont reconstruction Ansible). Scénario 6 adapté (révocation peer côté VPS hub). Concepts 14.2 et 14.3 réécrits (LiveBox 100% fermée, tunnels sortants), concept 14.9 entièrement refait en arbre de décision (4 options comparées, justification du choix relay). Nouveaux pièges en section 15 (SPOF VPS, procédure RESCUE oubliée, clé privée WG VPS). Schéma physique inline et fichier SVG mis à jour ("Modem only" au lieu de "Port fwd UDP/51820"). ADR `003-livebox-dmz-host-vs-bridge.md` renommé en `003-vps-relay-pour-admin-externe.md`. |

---

*Fin du document.*
