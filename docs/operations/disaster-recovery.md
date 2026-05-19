# Procédures de disaster recovery

> **Statut** : stub — à étoffer après le premier test fresh-install.
> **Auteur** : `ldesfontaine`

Ce document regroupera les procédures de récupération en cas
d'incident majeur : perte du VPS, perte de la machine de pilotage,
compromission de secrets, etc.

## Scénarios couverts (à venir)

- [ ] Perte totale du VPS Hetzner — redéploiement from scratch
  via les runbooks session-1 à 6.
- [ ] Perte de la machine de pilotage — récupération sur nouvelle
  machine (cf. `../secrets-inventory.md` §« Récupération sur
  nouvelle machine »).
- [ ] Compromission de la clé SSH `id_ed25519_homelab` —
  rotation immédiate (cf. `key-rotation.md`) + audit logs sshd VPS.
- [ ] Compromission du vault password — rotation
  `vault-pass-homelab.txt` + re-chiffrement de tous les vaults.
- [ ] Compromission d'un peer WireGuard — révocation peer +
  rotation pubkey hub si suspicion compromission hub.

## Procédure de redéploiement complet du VPS

Voir runbooks `docs/runbooks/session-{1..6}.md` dans l'ordre, plus
la récupération des secrets selon `../secrets-inventory.md`.

## Statut actuel

Procédures non encore testées dans des conditions de DR réel. La
roadmap §6 « Validation par test fresh-install » est l'occasion
prévue pour valider et étoffer ce document.
