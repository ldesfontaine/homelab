# Inventaire des secrets du homelab

> Doctrine et inventaire opérationnel : où vit chaque secret, comment
> le récupérer sur une nouvelle machine. La rotation détaillée des
> secrets vivra dans `docs/operations/key-rotation.md` (à livrer dans
> la phase 2 de la roadmap).

## Doctrine

**Dans le repo public** (chiffrés) :

- Secrets applicatifs Ansible (tokens API, mots de passe d'apps) →
  `ansible/inventory/group_vars/<group>/vault.yml` (ansible-vault,
  AES256).
- Backups OPNsense XML → `backups/opnsense/*.xml.age` (age).

**Hors repo** :

- Clés privées WireGuard et SSH (privkeys d'identité) →
  `~/homelab-keys/` (filesystem chiffré local).
- Passphrases (vault Ansible, clé age maître) → gestionnaire de mots
  de passe + backup cloud chiffré privé.

### Pourquoi les privkeys hors repo

Un repo Git public est append-only et définitif. Une fois publié,
même chiffré, le risque court rétrospectivement : si dans 10 ans la
passphrase fuite ou age est cassé, toutes les anciennes valeurs
chiffrées sont exposées. La convention DevSecOps appliquée ici :
pubkeys oui, secrets applicatifs chiffrés oui, privkeys d'identité
non.

L'option « tout chiffré dans le repo public, privkeys incluses » a
été évaluée et écartée pour trois raisons cumulatives : risque
rétrospectif irréversible (append-only), identification de cible
(repo public nommé `homelab` avec fichiers nommés `*.key.age`),
single point of failure passphrase.

## Inventaire

| Secret | Emplacement | Chiffrement | Backup |
|---|---|---|---|
| Vault password Ansible | `~/.ansible/vault-pass-homelab.txt` (`0600`) | filesystem | gestionnaire mdp |
| Clé age maître | `~/.age/homelab.key` (`0600`) | filesystem | gestionnaire mdp |
| Clé SSH homelab | `~/.ssh/id_ed25519_homelab` (`0600`) | filesystem | gestionnaire mdp |
| Clés WG peers admin | `~/homelab-keys/wg-admin-relay/*.key` (`0600`) | filesystem | archive `.tar.gz.age` sur cloud chiffré privé |
| Backups OPNsense | `backups/opnsense/*.xml.age` (in-repo) | age | repo Git + cloud chiffré |
| Tokens API (Cloudflare, etc.) | `ansible/inventory/group_vars/<group>/vault.yml` (in-repo) | ansible-vault AES256 | dans le vault |

## Procédure de récupération sur nouvelle machine

Hypothèse : nouvelle machine ou wipe complet du laptop. Prérequis :
compte gestionnaire de mots de passe accessible.

1. Installer le gestionnaire de mots de passe (Bitwarden, KeePassXC,
   etc.) et se connecter.
2. Récupérer depuis le gestionnaire et écrire en `chmod 600` :
   - `~/.ansible/vault-pass-homelab.txt` (mot de passe vault Ansible).
   - `~/.age/homelab.key` (clé age maître).
   - `~/.ssh/id_ed25519_homelab` (clé SSH homelab).
3. Récupérer l'archive `~/homelab-keys-backup.tar.gz.age` depuis le
   cloud chiffré privé. La déchiffrer et l'extraire :

   ```bash
   age -d -i ~/.age/homelab.key homelab-keys-backup.tar.gz.age | \
     tar xzf - -C ~/
   ```

   Vérifier que `~/homelab-keys/wg-admin-relay/*.key` est en place
   avec les bonnes permissions (`0600`).
4. Cloner le repo :

   ```bash
   git clone git@github.com:ldesfontaine/homelab.git
   cd homelab
   ```

5. Suivre la procédure « Setup local » du `README.md` (venv,
   `pip install -r ansible/requirements.txt`, collections galaxy via
   `ansible-galaxy collection install -r ansible/requirements.yml`,
   `pre-commit install`).
6. Vérifier la chaîne :
   - `ansible-vault view ansible/inventory/group_vars/vps/vault.yml`
     doit afficher le contenu déchiffré.
   - `pre-commit run --all-files` doit passer.

Si une étape échoue, voir le runbook correspondant dans
`docs/runbooks/`.

## Notes

- L'archive `.tar.gz.age` des privkeys WG est mise à jour
  manuellement après chaque rotation de clé. Une automatisation
  (`scripts/backup-wg-keys.sh`) est prévue (cf. roadmap §4 du
  project-overview).
- La rotation détaillée par type de secret (procédure pas-à-pas)
  vivra dans `docs/operations/key-rotation.md`, à livrer dans la
  phase 2 de la roadmap. En attendant, les principes généraux sont
  dans le project-overview §11 et dans ADR-000 Décision 8.
