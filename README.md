# Homelab

Mon Homelab est un environnement personnel en évolution continue. Il me sert à
héberger des services utiles, mais surtout à éprouver des choix
d’infrastructure dans des conditions réelles : déploiement, panne, reprise,
durcissement et maintenance dans le temps.

Ce dépôt documente l’architecture, l’automatisation et les procédures que je
travaille réellement dans mon Homelab. Il contient donc des choix concrets, des
schémas et certains éléments d’adressage. Les variables sensibles versionnées
sont chiffrées avec Ansible Vault et le dépôt est contrôlé avec Gitleaks.

## Ce que j’y travaille

- segmentation réseau et réduction de l’exposition ;
- automatisation avec Ansible et Infrastructure as Code ;
- durcissement des systèmes Linux et des accès SSH ;
- conteneurisation et publication maîtrisée des services ;
- observabilité, sauvegardes et procédures de reprise ;
- distinction entre ce qui est documenté, implémenté et réellement éprouvé.

## État du projet

Le Homelab n’est pas une architecture figée. Les services, les machines et les
outils peuvent évoluer lorsque les contraintes changent ou qu’une solution
plus simple remplace une première expérimentation.

Le dépôt [zero-trust](https://github.com/ldesfontaine/zero-trust) conserve une
expérimentation précédente autour d’une architecture Zero Trust. Il reste lié
à l’histoire du Homelab et montre une autre approche, mais il est désormais
archivé et ne décrit plus l’architecture actuelle.

Le travail réalisé dans cet environnement nourrit aujourd’hui Your Cloud, mon
projet principal de représentation, d’observation et d’évolution d’une
infrastructure depuis une interface compréhensible.

## Notes

Les décisions, limites et retours d’expérience sont publiés sous forme de
Notes :

- [Homelab : reprendre le contrôle de mes services](https://portfolio.ldesfontaine.com/notes/homelab-presentation)
- [Toutes les Notes](https://portfolio.ldesfontaine.com/notes)

## Licence

MIT — voir [`LICENSE`](LICENSE).
