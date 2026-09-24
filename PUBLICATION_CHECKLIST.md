# Publication checklist

Status on 2026-09-23: the application folder is **not a Git repository**. Its actual index/history could not be inspected. Ignore-rule verification is not proof that private files were never committed. No files have been published or private local files deleted by this preparation.

Before making any repository, screenshot set, ZIP or release public:

1. **Initialize or inspect Git.** Run `git rev-parse --show-toplevel`. If deliberately creating a repository, run `git init` only in the intended source directory; this does not audit earlier repositories or copies.
2. **Inspect status.** Run `git status --short --untracked-files=all`; review every intended addition. Do not blindly add the whole working directory.
3. **Inspect tracked and staged files.** Run `git ls-files` and `git diff --cached --name-only`. Review the staged diff locally for private content. Verify rules with `git check-ignore -v --no-index <path>`. Ignore rules do not untrack existing files.
4. **Inspect history before publication.** Review all branches/tags and `git log --all --name-only --format=oneline`, including deleted or renamed files. Inspect release-archive contents too. Resolve exposures before publishing; do not assert clean history without inspection.
5. **Confirm the private DB was never committed.** Search actual tracked files and all relevant history for databases, WAL/SHM, backups and health exports, including renamed files. Confirm no private observations/notes occur in source fixtures or docs. If evidence is absent, mark this unverified rather than complete.
6. **Confirm no secrets or private configuration.** Inspect staged files/history for credentials, tokens, .env, private keys and personal coordinates/settings. Example files must contain placeholders/public examples only. Current public Open-Meteo calls need no stored API key. Do not print discovered secrets in public reports.
7. **Use synthetic-only public screenshots.** Use a separate initialized demo database without real observations. Check visible notes, dates, browser tabs and filesystem paths. A mixed-dataset badge does not anonymize real data. Work/output/browser artifacts are ignored by default; review any deliberately selected public image.
8. **Perform a clean-clone/source-only setup test.** From the intended source revision in a new directory, create a fresh Python environment, install pinned requirements, run `npm.cmd ci`, initialize an empty DB, generate only synthetic data, then run both test suites and the build. Do not copy private DB/backups/.env/venv/node_modules. Record revision and installation limitations. A source-only check using existing dependencies is useful but is not a fresh-install/clean-clone test.
9. **Record versions.** Save `python --version`, `node --version`, npm version and source revision. This workstation used Python **3.12.14**, Node **v24.19.0** for the IMPORTANT fixes; reconfirm in the clean setup.
10. **Record synthetic provenance.** Specify generator revision, seed **42**, demonstration symptom end date **2026-09-18 UTC**, and daily-health seed **42**. Keep synthetic labels. Moving default dates, database IDs and actual creation timestamps do not guarantee identical regeneration.

Excluded by default: SQLite/journals, backups, .env* except a reviewed .env.example, local/private configuration, data/private/generated/raw/processed/exports, work, outputs, screenshots and browser artifacts. Never publish an unfiltered whole-directory ZIP. Do not delete private local files as a publication shortcut.

Actual repository-history clearance and a clean-clone release check remain pending until a publication candidate exists.
