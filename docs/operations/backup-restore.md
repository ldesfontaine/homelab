# Procédures de backup et restauration

> **Statut** : stub — à étoffer quand la stratégie PBS sera en place.
> **Auteur** : `ldesfontaine`

Ce document regroupera les procédures de backup et de restauration
pour chaque composant du homelab.

## Composants concernés

- VPS : `/opt/pangolin/config/` (Pangolin DB + acme.json),
  `/opt/crowdsec/{config,data}/`, vault Ansible.
- Portfolio : volumes `portfolio-data` (SQLite) et `portfolio-media`.
- OPNsense (à venir) : config XML, backups age déjà présents dans
  `backups/`.
- Proxmox (à venir) : configs LXC/VM via PBS.
- Vaultwarden, Filebrowser, Authentik (à venir) : volumes Docker.

## Stratégie cible — 3-2-1

- 3 copies des données
- 2 supports différents
- 1 copie off-site (cloud chiffré age)

## Procédures (à venir)

- [ ] Snapshot manuel Pangolin
- [ ] Snapshot manuel portfolio (via UI Payload `/admin`)
- [ ] Backup/restore OPNsense (cf. backups age existants)
- [ ] PBS — backups LXC/VMs Proxmox
- [ ] Restauration sur nouveau VPS (test DR)

## Statut actuel

Backups Pangolin et portfolio : **manuels uniquement** (cf.
runbooks session-3 §4.9 et session-4 §6). Pas de cron host-side.
PBS et automatisation : roadmap phase 7.
