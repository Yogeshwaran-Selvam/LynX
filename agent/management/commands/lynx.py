"""
LynX CLI — manage installations, trigger analysis, inspect context.

Usage:
    python manage.py lynx installations              List all installations
    python manage.py lynx repos <installation_id>    List repos for an installation
    python manage.py lynx run <owner/repo>           Run the full analysis pipeline
    python manage.py lynx context <owner/repo>       View stored context for a repo
    python manage.py lynx prefs <installation_id>    View user preferences
"""

import json
import requests
from django.core.management.base import BaseCommand
from agent.repo_reader import _get_jwt_token, _get_installation_token, _headers
from agent.pipeline import analyze_repo
from agent import context_store


class Command(BaseCommand):
    help = "LynX CLI — manage installations and trigger the pipeline"

    def add_arguments(self, parser):
        parser.add_argument("action",
                            choices=["installations", "repos", "run", "context", "prefs"],
                            help="Action to perform")
        parser.add_argument("target", nargs="?", default=None,
                            help="Installation ID or owner/repo depending on action")

    def handle(self, *args, **options):
        action = options["action"]
        target = options["target"]

        if action == "installations":
            self._list_installations()
        elif action == "repos":
            if not target:
                self.stderr.write("Usage: python manage.py lynx repos <installation_id>")
                return
            self._list_repos(int(target))
        elif action == "run":
            if not target or "/" not in target:
                self.stderr.write("Usage: python manage.py lynx run <owner/repo>")
                return
            self._run_pipeline(target)
        elif action == "context":
            if not target or "/" not in target:
                self.stderr.write("Usage: python manage.py lynx context <owner/repo>")
                return
            self._show_context(target)
        elif action == "prefs":
            if not target:
                self.stderr.write("Usage: python manage.py lynx prefs <installation_id>")
                return
            self._show_prefs(int(target))

    def _list_installations(self):
        jwt_token = _get_jwt_token()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        }
        resp = requests.get("https://api.github.com/app/installations", headers=headers)
        resp.raise_for_status()

        installations = resp.json()
        if not installations:
            self.stdout.write("No installations found.")
            return

        self.stdout.write(f"\n{'ID':<15} {'Account':<25} {'Repos':<15}")
        self.stdout.write("-" * 55)
        for inst in installations:
            account = inst["account"]["login"]
            selection = inst["repository_selection"]
            inst_id = inst["id"]
            self.stdout.write(f"{inst_id:<15} {account:<25} {selection:<15}")

            # Show analyzed repos from local context
            analyzed = context_store.list_repos(inst_id)
            if analyzed:
                self.stdout.write(f"  Analyzed: {', '.join(analyzed)}")

        self.stdout.write(f"\nUsage: python manage.py lynx repos <ID>")

    def _list_repos(self, installation_id):
        token = _get_installation_token(installation_id)
        resp = requests.get(
            "https://api.github.com/installation/repositories",
            headers=_headers(token),
        )
        resp.raise_for_status()

        repos = resp.json().get("repositories", [])
        if not repos:
            self.stdout.write("No repos accessible to this installation.")
            return

        self.stdout.write(f"\nRepos for installation {installation_id}:\n")
        for repo in repos:
            full_name = repo["full_name"]
            owner, name = full_name.split("/", 1)
            meta = context_store.read_metadata(installation_id, owner, name)
            status = meta.get("status", "not analyzed") if meta else "not analyzed"
            marker = "+" if status == "complete" else "-"
            self.stdout.write(f"  [{marker}] {full_name:<40} {status}")

        self.stdout.write(f"\nUsage: python manage.py lynx run <owner/repo>")

    def _run_pipeline(self, full_name):
        owner, repo = full_name.split("/", 1)

        # Find the installation for this repo
        jwt_token = _get_jwt_token()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        }
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/installation",
            headers=headers,
        )
        if resp.status_code == 404:
            self.stderr.write(f"LynX is not installed on {full_name}.")
            return
        resp.raise_for_status()
        installation_id = resp.json()["id"]

        self.stdout.write(f"\nRunning LynX pipeline on {full_name} (installation: {installation_id})\n")
        # Pipeline prints the full narrative via _print_narrative
        analyze_repo(installation_id, owner, repo, force=True)
        self.stdout.write(f"\nContext stored and encrypted.")

    def _show_context(self, full_name):
        owner, repo = full_name.split("/", 1)

        # Find installation
        jwt_token = _get_jwt_token()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        }
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/installation",
            headers=headers,
        )
        if resp.status_code == 404:
            self.stderr.write(f"LynX is not installed on {full_name}.")
            return
        resp.raise_for_status()
        installation_id = resp.json()["id"]

        meta = context_store.read_metadata(installation_id, owner, repo)
        if not meta:
            self.stdout.write(f"No context stored for {full_name}. Run: python manage.py lynx run {full_name}")
            return

        self.stdout.write(f"\n--- Metadata for {full_name} ---")
        self.stdout.write(json.dumps(meta, indent=2))

        ctx = context_store.read_repo_context(installation_id, owner, repo)
        if ctx:
            understanding = ctx.get("understanding", {})
            self.stdout.write(f"\n--- Understanding ---")
            self.stdout.write(json.dumps(understanding, indent=2))
        else:
            self.stdout.write(f"\nNo encrypted context found.")

    def _show_prefs(self, installation_id):
        prefs = context_store.read_user_preferences(installation_id)
        if not prefs:
            self.stdout.write(f"No preferences stored for installation {installation_id}.")
            return

        self.stdout.write(f"\n--- User Preferences (installation {installation_id}) ---")
        self.stdout.write(json.dumps(prefs, indent=2))
