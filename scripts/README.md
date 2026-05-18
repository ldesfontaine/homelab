# scripts/

Scripts utilitaires locaux au laptop Lucas. Ne sont pas joués sur les hôtes
distants (ce n'est pas Ansible).

## Scripts disponibles

| Script                         | Rôle                                                     |
|--------------------------------|----------------------------------------------------------|
| `wg-admin-gen-profile.py`      | Génère les profils WG ADMIN-RELAY (laptop, phone, tablet) |

Voir la doc de chaque script :
- `wg-admin-gen-profile.py` → [docs/wg-admin-profiles.md](../docs/wg-admin-profiles.md)

## Convention

Les scripts versionnés ici doivent :
- Ne consommer aucun secret depuis le repo (lire les secrets depuis
  `~/homelab-keys/` ou `~/.ansible/` qui sont hors repo)
- Être idempotents quand c'est pertinent
- Avoir un `--help` ou docstring expliquant l'usage
- Préférer Python (cohérent avec l'écosystème Ansible/Jinja2 du projet)
