# Procédures de rotation des secrets

> **Statut** : stub — à étoffer au fur et à mesure des rotations.
> **Auteur** : `ldesfontaine`

Ce document regroupera les procédures pas-à-pas de rotation pour
chaque type de secret du homelab. À étoffer au moment de chaque
rotation effective : c'est ce qu'on fait qu'on documente, pas ce
qu'on imagine faire.

## Secrets concernés

Inventaire complet dans [`../secrets-inventory.md`](../secrets-inventory.md).

- Clés WireGuard admin (hub VPS + peers laptop/phone) — premier
  full rotate documenté au Lot suivant.
- Clé SSH `id_ed25519_homelab` — rotation à chaque compromission
  potentielle de la machine de pilotage.
- Vault password Ansible — rotation annuelle ou sur compromission
  gestionnaire de mots de passe.
- Token Cloudflare API — rotation annuelle.
- Token GHCR — rotation annuelle.
- Secrets applicatifs (Payload, Pangolin admin, etc.) — selon
  doctrine de chaque service.

## Procédures (à venir)

- [ ] Rotation full des clés WireGuard admin (hub + tous peers)
- [ ] Rotation clé SSH `id_ed25519_homelab`
- [ ] Rotation vault password Ansible
- [ ] Rotation token Cloudflare API
- [ ] Rotation token GHCR

## Principes généraux

Voir [project-overview §11](../00-project-overview.md) et
[ADR-000 Décision 8](../adr/ADR-000-fondations-ansible.md).
