# Documentation du Homelab

## Commencer ici

- [`ETAT-DU-PROJET.md`](ETAT-DU-PROJET.md) : état réel et prochaine étape.
- [`CHOIX-STRUCTURANTS.md`](CHOIX-STRUCTURANTS.md) : décisions retenues et
  raisons courtes.

## Architecture

- [`architecture/vue-ensemble.md`](architecture/vue-ensemble.md)
- [`architecture/cablage.md`](architecture/cablage.md)
- [`architecture/zones-et-vlans.md`](architecture/zones-et-vlans.md)
- [`architecture/politique-firewall.md`](architecture/politique-firewall.md)

## Inventaire

- [`inventaire/materiel.md`](inventaire/materiel.md)

## Mise en place

Les runbooks sont ajoutés uniquement lorsque leur phase commence. La première
partie couvre actuellement :

- [`runbooks/01-preparer-et-identifier.md`](runbooks/01-preparer-et-identifier.md)
- [`runbooks/02-installer-opnsense.md`](runbooks/02-installer-opnsense.md)
- [`runbooks/03-configurer-switch-et-vlans.md`](runbooks/03-configurer-switch-et-vlans.md)
- [`runbooks/04-valider-le-socle-reseau.md`](runbooks/04-valider-le-socle-reseau.md)

Chaque runbook contient ses propres contrôles et son retour arrière. Un dossier
de preuves séparé n’est pas nécessaire tant que les validations restent
lisibles dans les procédures et dans l’état du projet.
