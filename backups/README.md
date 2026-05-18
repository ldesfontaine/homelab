# backups/

Backups chiffrés du homelab. Convention :

- OPNsense XML : `opnsense/*.xml.age` (chiffrement age, clé maître
  `~/.age/homelab.key`).
- Autres types à venir (Proxmox, Vaultwarden, etc.) : un sous-dossier
  par service, fichiers chiffrés age.

Les fichiers en clair ne sont jamais commités. La chaîne pre-commit
(gitleaks + detect-private-key) en est garante.

Voir [`docs/secrets-inventory.md`](../docs/secrets-inventory.md) pour
la doctrine secrets et la procédure de récupération sur nouvelle
machine.
