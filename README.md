# Homelab

Mon Homelab est un environnement personnel en évolution continue. Il me sert à
héberger des services utiles, mais surtout à éprouver des choix
d’infrastructure dans des conditions réelles : déploiement, panne, reprise,
durcissement et maintenance dans le temps.

Ce dépôt documente ce qui existe réellement, les choix structurants et les
procédures permettant de reconstruire l’infrastructure. Il ne présente pas une
intention comme un résultat : chaque étape reste distinguée entre
**planifiée**, **configurée** et **validée**.

## Repartir du réseau

L’ancien Homelab est considéré comme indisponible. Sa configuration VPS et son
automatisation restent consultables dans l’historique Git, au tag
`ancien-homelab-2026`, mais elles ne décrivent plus l’infrastructure actuelle.

La reconstruction suit trois parties :

1. mettre en place OPNsense, le switch et la segmentation réseau ;
2. installer Proxmox et un premier service de test ;
3. intégrer progressivement le Homelab avec Your Cloud.

Le Wi-Fi reste temporairement géré par la Livebox. La future borne sera
raccordée manuellement au réseau prévu pour elle ; sa configuration n’appartient
pas à la première partie.

## Rôle du dépôt

Le dépôt est le dossier technique public du Homelab :

- architecture physique et logique ;
- inventaire sans numéros de série, adresses MAC ni secrets ;
- journal court des choix structurants ;
- procédures de mise en place, de validation et de retour arrière ;
- sauvegardes de configuration uniquement sous forme chiffrée.

Le point d’entrée opérationnel est
[`docs/ETAT-DU-PROJET.md`](docs/ETAT-DU-PROJET.md).

## Histoire du projet

Le dépôt [zero-trust](https://github.com/ldesfontaine/zero-trust) conserve une
expérimentation précédente autour d’une architecture Zero Trust. Il reste lié à
l’histoire du Homelab, mais ne décrit plus l’architecture actuelle.

Le travail réalisé ici nourrit également
[Your Cloud](https://github.com/ldesfontaine/your-cloud), le projet de
représentation, d’observation et d’évolution compréhensible d’une
infrastructure. Le Homelab reste néanmoins autonome : son réseau doit continuer
à fonctionner lorsque Your Cloud est absent.

## Notes

- [Homelab : reprendre le contrôle de mes services](https://portfolio.ldesfontaine.com/notes/homelab-presentation)
- [Toutes les Notes](https://portfolio.ldesfontaine.com/notes)

## Licence

MIT — voir [`LICENSE`](LICENSE).
