#!/usr/bin/env bash
# scripts/setup.sh — bootstrap d'un clone du repo homelab.
#
# Idempotent : peut être lancé plusieurs fois sans casser un setup
# existant. Pip skip ce qui est déjà installé, ansible-galaxy
# détecte les collections présentes, pre-commit install est
# idempotent par design.
#
# Référence : README.md section "Setup local".

set -euo pipefail

echo "[1/4] Création du venv Python et installation des dépendances..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r ansible/requirements.txt

echo "[2/4] Installation des collections Ansible..."
.venv/bin/ansible-galaxy collection install -r ansible/requirements.yml

echo "[3/4] Installation des hooks pre-commit..."
.venv/bin/pre-commit install --install-hooks

echo "[4/4] Vérification de la chaîne..."
.venv/bin/pre-commit run --all-files || {
  echo ""
  echo "Warning: pre-commit run --all-files a échoué."
  echo "Vérifie le vault password file (~/.ansible/vault-pass-homelab.txt)."
  echo "Voir docs/secrets-inventory.md pour la procédure de récupération."
}

echo ""
echo "✅ Setup terminé. Voir docs/secrets-inventory.md pour la configuration des secrets."
