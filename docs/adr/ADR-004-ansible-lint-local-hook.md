# ADR-004 — Invocation d'ansible-lint via hook pre-commit local

> **Statut** : actif — `v1.0` — auteur `ldesfontaine`
> **Date** : 2026-05-18
> **Supersede** : aucun
> **Contexte d'origine** : Lot 2.0quater de la séquence pré-republication

---

## Contexte

Le repo héberge un projet Ansible sous `ansible/` (`ansible.cfg`,
`roles/`, `playbooks/`, `inventory/`). Le `ansible.cfg` y déclare
`roles_path = ./roles` relatif à ce dossier — convention Ansible
standard.

Le hook pre-commit upstream officiel `ansible/ansible-lint` (référencé
par `repo: https://github.com/ansible/ansible-lint` dans
`.pre-commit-config.yaml`) exécute ansible-lint depuis la **racine
du repo Git**, pas depuis `ansible/`. Conséquence : `ansible.cfg`
n'est pas chargé, `roles_path` n'est pas résolu, et ansible-lint
échoue avec des erreurs `syntax-check[specific]` sur les rôles
référencés depuis les playbooks (rôles introuvables dans les chemins
par défaut).

## Décision

Le hook pre-commit `ansible-lint` est défini comme **hook local**
dans `.pre-commit-config.yaml` :

```yaml
- repo: local
  hooks:
    - id: ansible-lint
      name: ansible-lint (from ansible/)
      language: system
      entry: bash -c 'cd ansible && exec ../.venv/bin/ansible-lint "$@"' --
      files: ^ansible/
      pass_filenames: false
```

Le hook fait `cd ansible` avant d'exécuter `ansible-lint`. Ansible
trouve alors `ansible.cfg` par autodétection (cwd) et résout
`roles_path` correctement.

Le fichier `.ansible-lint` vit dans `ansible/` (et non à la racine
du repo) pour cohérence : les configurations Ansible (cfg, lint)
sont groupées au même endroit, les `exclude_paths` du `.ansible-lint`
sont interprétés relativement au project_dir Ansible.

La version d'ansible-lint utilisée est celle du venv du projet
(`.venv/bin/ansible-lint`), pinned via `ansible/requirements.txt`.
La `rev:` du hook upstream est abandonnée — une seule source de
vérité pour la version d'ansible-lint, alignée entre invocation
manuelle, hook pre-commit, et future CI éventuelle.

## Alternatives évaluées

### A. Conserver le hook upstream avec `args: [--project-dir, ansible/]`

Rejetée. Diagnostic Lot 2.0quater : le flag `--project-dir`
d'ansible-lint définit le project root pour la résolution interne
des chemins, mais **ne déclenche pas le chargement de `ansible.cfg`**.
Les erreurs `syntax-check[specific]` persistent. De plus, ce mode
expose ansible-lint au scan complet de `ansible/.collections/`
(collections vendored), générant ~19 000 violations de bruit.

### B. Conserver le hook upstream avec un `.ansible-lint` à la racine
qui dupliquerait la topologie

Rejetée. Duplication de la connaissance « le projet Ansible est dans
`ansible/` » entre `ansible/ansible.cfg` et `.ansible-lint` racine.
Source future de divergence si la topologie évolue. Viole DRY.

### C. Wrapper script `scripts/lint-ansible.sh` appelé par le hook

Rejetée. Indirection supplémentaire sans bénéfice : le hook `bash -c`
fait déjà le job en une ligne, lisible et auto-documenté.

## Conséquences

### Positives

- Le hook reproduit exactement l'invocation manuelle (`cd ansible &&
  ansible-lint`) — comportement identique entre dev et CI.
- Source unique de la version d'ansible-lint (le venv via
  `requirements.txt`) — élimine la classe de bugs « divergence rev:
  pre-commit vs version pip » qui a causé l'incident du Lot 2.0bis
  (tag `v25.0.1` inexistant upstream).
- Pas de duplication de configuration de topologie.

### Négatives

- Dépendance dure au venv : le hook ne fonctionne pas tant que
  `scripts/setup.sh` n'a pas été exécuté. Atténuation : le `setup.sh`
  est documenté en première étape post-clone dans le README, et son
  appel installe le hook git pre-commit dans la foulée.
- Perte de l'auto-update via `pre-commit autoupdate` pour ce hook
  spécifique. La mise à jour d'ansible-lint passe désormais par
  `ansible/requirements.txt`. Acceptable : le pin de version est
  centralisé là, pas dispersé entre deux fichiers.
- Le hook tourne en `language: system`, donc pas dans un env
  pre-commit isolé. Bénin tant que le venv est sain ; en pratique
  c'est l'usage manuel reproduit, donc la rigueur est la même qu'à
  l'usage humain.

## Vérification

`pre-commit run ansible-lint --all-files` doit retourner `Passed`
sur un repo dont le venv est setup et qui respecte la doctrine
Ansible. Validé au Lot 2.0quater (0 violation, 0 warning sur 121
fichiers en profil `production`).

---

## Changelog

| Date       | Version | Changement                |
|------------|---------|---------------------------|
| 2026-05-18 | 1.0     | Création initiale (post Lot 2.0quater) |
