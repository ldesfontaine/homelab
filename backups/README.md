# Sauvegardes de configuration

Les exports OPNsense et Netgear peuvent contenir des informations sensibles :
comptes, empreintes, topologie, adresses ou clés. Ils ne sont jamais versionnés
en clair.

## Convention

```text
backups/
├── opnsense/
│   └── config-AAAA-MM-JJ.xml.age
└── switch/
    └── config-AAAA-MM-JJ.cfg.age
```

- chiffrement externe avec `age` avant toute copie dans le dépôt ;
- clé privée de déchiffrement conservée hors du dépôt ;
- aucune adresse MAC, clé privée ou phrase secrète dans les noms de fichiers ;
- une seconde copie chiffrée doit exister hors Git ;
- une sauvegarde n’est considérée comme utile qu’après un test de restauration.

Les commandes exactes de sauvegarde et de restauration seront écrites au
moment de la première exportation réelle. Aucun exemple ne doit inclure un
secret utilisable.
