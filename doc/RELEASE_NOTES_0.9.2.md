# ConvertAll 0.9.2 — notes de version

À compléter avant publication. Contenu depuis v0.9.1 :

- Add tools/bump_version.py so a version bump cannot miss a pinned copy
- [PROD] Validate this tree for the release
- Fix the env filter that stored the literal "$NEW_EMAIL" as the author address
- Look for the tooling identity on either side of a commit
- Read raw identities in the author-rewrite report
- Add .mailmap and tools/rewrite_authors.sh to settle commit authorship
- [PROD] Validate this tree for the release
- Make the comments column follow the list width instead of its content
- Add run_qt6.sh, the missing launcher for the application itself
- Spec a Rust CLI for the unit converter: doc/CLI_RUST_CAHIER_DES_CHARGES.md
- Decide the CI run before anything reads it, fixing the release preflight
- Accept an exported .deb maintainer and explain the failure that stopped the release
- [PROD] Validate this tree for the 0.9.1 release
- [PROD] Validate this tree for the 0.9.1 release
- Add a local rehearsal mode that never touches CI or releases

## Points à vérifier à la main

- bureau réel, DPI et GPU : non certifiés par la CI ;
- installation, mise à niveau et désinstallation du `.deb` ;
- AppImage : double-clic (AppImageLauncher ne lit pas le zstd, voir doc/RELEASE_LINUX_FR.md) ;
- licences et attributions.
