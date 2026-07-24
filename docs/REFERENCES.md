# Références techniques

Recherche vérifiée le 24 juillet 2026. Les procédures du dépôt s’appuient
d’abord sur les documentations des éditeurs, pas sur des tutoriels tiers.

## OPNsense

- [installation officielle](https://docs.opnsense.org/manual/install.html) ;
- [configuration des interfaces](https://docs.opnsense.org/manual/interfaces.html) ;
- [VLAN et trunks 802.1Q](https://docs.opnsense.org/manual/how-tos/vlan_and_lagg.html) ;
- [ordre et fonctionnement des règles firewall](https://docs.opnsense.org/manual/firewall.html) ;
- [Unbound et DNS over TLS](https://docs.opnsense.org/manual/unbound.html) ;
- [Dnsmasq pour DHCP et DNS](https://docs.opnsense.org/manual/dnsmasq.html) ;
- [service NTP](https://docs.opnsense.org/manual/ntpd.html) ;
- [sauvegarde et restauration](https://docs.opnsense.org/manual/backups.html) ;
- [restauration depuis la console](https://docs.opnsense.org/troubleshooting/config_reset.html) ;
- [zones de sécurité](https://docs.opnsense.org/manual/how-tos/security-zones.html).
- [prise en charge Intel i226 par le pilote FreeBSD `igc`](https://lists.freebsd.org/archives/dev-commits-src-all/2024-December/049940.html).

## Accès Internet et DNS

- [Orange — réserver une adresse à un équipement sur Livebox 6/7](https://assistance.orange.fr/livebox-modem/toutes-les-livebox-et-modems/installer-et-utiliser/piloter-et-parametrer-votre-materiel/le-parametrage-avance-reseau-nat-pat-ip/creer-un-reseau-local-a-votre-domicile/livebox-6-attribuer-une-ip-fixe-a-un-equipement_362611-896056/1000) ;
- [Orange — réseau DHCP par défaut de la Livebox](https://assistance.orange.fr/livebox-modem/toutes-les-livebox-et-modems/depanner/un-probleme-d-acces-a-internet/aucune-connexion/livebox-activer-le-serveur-dhcp_438258-967800) ;
- [Quad9 — adresses et politiques des services](https://docs.quad9.net/services/) ;
- [Quad9 — tests d’utilisation et de protocole](https://docs.quad9.net/fr/FAQ/) ;
- [Quad9 — pratiques pour un forwarder DNS](https://docs.quad9.net/Quad9_For_Organizations/DNS_Forwarder_Best_Practices/) ;
- [RFC 8375 — domaine privé `home.arpa`](https://www.rfc-editor.org/info/rfc8375/).

## Switch

- [manuel officiel NETGEAR MS305E/MS308E](https://www.downloads.netgear.com/files/GDC/MS305E/MS305E_MS308E_UM_EN.pdf).

Le manuel décrit les VLAN 802.1Q, les PVID, la sauvegarde, le contrôle d’accès
par adresse IP et le reset physique. Il ne décrit pas de VLAN de management
dédié pour le MS305E : le dépôt n’en suppose donc pas l’existence.
