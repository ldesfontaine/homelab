#!/usr/bin/env python3
"""Génère les profils WireGuard ADMIN-RELAY pour les peers app du homelab.

Source de vérité : scripts/wg-admin-profiles.yml
Template         : scripts/templates/wg-admin-client.conf.j2
Output           : ~/homelab/keys/wg-admin-relay/profiles/<peer>.{conf,png}

Les clés privées sont lues à la volée depuis ~/homelab/keys/wg-admin-relay/<peer>.key
et n'apparaissent jamais dans le repo.

Voir docs/wg-admin-profiles.md pour la doctrine complète.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
CONFIG_FILE = SCRIPTS_DIR / "wg-admin-profiles.yml"
TEMPLATE_DIR = SCRIPTS_DIR / "templates"
TEMPLATE_NAME = "wg-admin-client.conf.j2"

KEYS_DIR = Path.home() / "homelab" / "keys" / "wg-admin-relay"
PROFILES_DIR = KEYS_DIR / "profiles"


def load_config() -> dict:
    if not CONFIG_FILE.is_file():
        sys.exit(f"❌ Config introuvable: {CONFIG_FILE}")
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_private_key(peer_name: str) -> str:
    key_file = KEYS_DIR / f"{peer_name}.key"
    if not key_file.is_file():
        sys.exit(f"❌ Clé privée introuvable: {key_file}")
    key = key_file.read_text(encoding="utf-8").strip()
    if not key:
        sys.exit(f"❌ Clé privée vide: {key_file}")
    return key


def render_profile(config: dict, peer: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(TEMPLATE_NAME)
    return template.render(
        peer=peer,
        hub=config["hub"],
        private_key=load_private_key(peer["name"]),
    )


def write_profile(peer_name: str, content: str) -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.chmod(0o700)
    out_file = PROFILES_DIR / f"{peer_name}.conf"
    out_file.write_text(content, encoding="utf-8")
    out_file.chmod(0o600)
    return out_file


def generate_qr_code(conf_file: Path) -> Path | None:
    if not shutil.which("qrencode"):
        return None
    qr_file = conf_file.with_suffix(".png")
    subprocess.run(
        ["qrencode", "-t", "PNG", "-o", str(qr_file), "-r", str(conf_file)],
        check=True,
    )
    qr_file.chmod(0o600)
    return qr_file


def generate_for_peer(config: dict, peer_name: str) -> None:
    peers = {p["name"]: p for p in config["peers"]}
    if peer_name not in peers:
        available = ", ".join(sorted(peers))
        sys.exit(f"❌ Peer inconnu: {peer_name}\n   Peers déclarés: {available}")
    peer = peers[peer_name]
    content = render_profile(config, peer)
    conf_file = write_profile(peer_name, content)
    qr_file = generate_qr_code(conf_file)

    print(f"✅ Profil généré: {conf_file}")
    print(f"   Tunnel IP    : {peer['tunnel_ip']}")
    print(f"   AllowedIPs   : {peer['allowed_ips']}")
    if qr_file:
        print(f"   QR PNG       : {qr_file}")
        print("")
        print(f"   Afficher en terminal :")
        print(f"     qrencode -t ANSIUTF8 -r {conf_file}")
    else:
        print("   ⚠️  qrencode non installé — PNG non généré.")
        print("       Installer : sudo apt install qrencode")


def list_peers(config: dict) -> None:
    print("Peers déclarés dans scripts/wg-admin-profiles.yml :\n")
    for peer in config["peers"]:
        devices = ", ".join(peer.get("devices", [])) or "—"
        print(f"  • {peer['name']:<8}  {peer['tunnel_ip']:<18}  {devices}")
    print(f"\nHub : {config['hub']['endpoint']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Génère les profils WG ADMIN-RELAY des peers app.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  %(prog)s --list           # liste les peers déclarés\n"
            "  %(prog)s phone            # génère le profil phone\n"
            "  %(prog)s --all            # génère tous les profils\n"
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("peer", nargs="?", help="Nom du peer (laptop, phone, tablet)")
    group.add_argument("--all", action="store_true", help="Génère tous les peers")
    group.add_argument("--list", action="store_true", help="Liste les peers déclarés")

    args = parser.parse_args()
    config = load_config()

    if args.list:
        list_peers(config)
        return 0

    if args.all:
        for peer in config["peers"]:
            generate_for_peer(config, peer["name"])
            print()
        return 0

    generate_for_peer(config, args.peer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
