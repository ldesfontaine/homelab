# ADR 001 — Stack technique initiale

## Statut
Accepté, 2026-05-11

## Contexte
Construction d'un homelab familial avec contraintes : souveraineté, IaC, sécu, budget contenu.

## Décisions

### Hyperviseur : Proxmox VE
Vs ESXi : open source, communauté active, intégration LXC native, PBS associé.
Vs XCP-ng : moins répandu en homelab, écosystème moins fourni.

### Firewall : OPNsense
Vs pfSense : licence plus claire (BSD), UI moderne, plugins natifs (CrowdSec, Suricata, WireGuard).

### Reverse proxy public : Pangolin (Fossorial)
Vs Cloudflare Tunnel : self-hosted, pas de dépendance SaaS proprio, contrôle total.

### IDP : Authentik
Vs Keycloak : plus moderne, UI plus claire, plugins suffisants pour homelab.
Vs Authelia : moins de fonctionnalités OIDC complètes.

### Coffre mots de passe : Vaultwarden
Vs Bitwarden self-hosted : plus léger (Rust vs Java), compatible clients officiels.

### IaC : Ansible
Vs Terraform : Ansible suffit pour la config (Terraform serait sur-engineered pour 5 LXCs).

## Conséquences
- Maintenance d'un stack open-source diversifié
- Engagement à apprendre Ansible en profondeur
- Repo Git source de vérité
