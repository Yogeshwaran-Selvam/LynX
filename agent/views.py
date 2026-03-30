import hashlib
import hmac
import json
import logging
import os
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from dotenv import load_dotenv
from . import tasks
from . import context_store
from .pipeline import analyze_repo, analyze_repos_batch

load_dotenv()

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")


def _verify_signature(request) -> bool:
    """Verify GitHub webhook signature (X-Hub-Signature-256)."""
    if not WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature:
        logger.warning("Webhook missing X-Hub-Signature-256 header")
        return False

    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        request.body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


def home(request):
    return HttpResponse("LynX Webhook Server is running!")


@csrf_exempt
@require_POST
def webhook(request):
    if not _verify_signature(request):
        logger.warning("Webhook signature verification failed")
        return HttpResponse("Invalid signature", status=403)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event = request.headers.get("X-GitHub-Event", "")
    logger.info(f"\n--- WEBHOOK RECEIVED: {event} ---")

    # ── Ping ─────────────────────────────────────────────────
    if event == "ping":
        logger.info(f"GitHub Zen: {payload.get('zen')}")
        return JsonResponse({"status": "pong"})

    # ── Installation (app installed/uninstalled) ─────────────
    if event == "installation":
        action = payload.get("action")  # created, deleted
        installation_id = payload["installation"]["id"]
        sender = payload.get("sender", {}).get("login")
        repos = payload.get("repositories", [])
        repo_names = [r["full_name"] for r in repos]
        logger.info(f"App {action} by {sender} on repos: {repo_names}")

        # Auto-analyze repos on fresh install
        if action == "created" and repos:
            repo_tuples = [(r["full_name"].split("/")[0], r["full_name"].split("/")[1]) for r in repos]
            logger.info(f"Dispatching background analysis for {len(repo_tuples)} repo(s)...")
            tasks.submit(analyze_repos_batch, installation_id, repo_tuples)
            return JsonResponse({"status": "accepted", "analyzing": repo_names}, status=202)

        return JsonResponse({"status": "ok", "action": action})

    # ── Installation repos (repos added/removed) ─────────────
    if event == "installation_repositories":
        action = payload.get("action")  # added, removed
        installation_id = payload["installation"]["id"]
        added = payload.get("repositories_added", [])
        removed = payload.get("repositories_removed", [])
        added_names = [r["full_name"] for r in added]
        removed_names = [r["full_name"] for r in removed]
        logger.info(f"Repos updated — added: {added_names}, removed: {removed_names}")

        # Auto-analyze newly added repos in background
        if added:
            repo_tuples = [(r["full_name"].split("/")[0], r["full_name"].split("/")[1]) for r in added]
            logger.info(f"Dispatching background analysis for {len(repo_tuples)} new repo(s)...")
            tasks.submit(analyze_repos_batch, installation_id, repo_tuples)

        # Clean up context for removed repos
        if removed:
            for r in removed:
                owner, repo = r["full_name"].split("/", 1)
                context_store.delete_repo_context(installation_id, owner, repo)
                logger.info(f"Deleted context for {r['full_name']}")

        return JsonResponse({
            "status": "accepted",
            "analyzing": added_names,
            "cleaned": removed_names,
        }, status=202)

    # ── Pull Request ─────────────────────────────────────────
    if event == "pull_request":
        action = payload.get("action")
        pr_title = payload.get("pull_request", {}).get("title")
        logger.info(f"Pull Request {action}: {pr_title}")
        return JsonResponse({"status": "noted", "action": action})

    # ── Push (re-analyze on push to main/master) ─────────────
    if event == "push":
        ref = payload.get("ref", "")
        if ref not in ("refs/heads/main", "refs/heads/master"):
            return HttpResponse(status=200)

        owner = payload["repository"]["owner"]["login"]
        repo_name = payload["repository"]["name"]
        installation_id = payload["installation"]["id"]
        pusher = payload.get("pusher", {}).get("name")

        logger.info(f"Push on {owner}/{repo_name} by {pusher} — re-analyzing...")
        tasks.submit(analyze_repo, installation_id, owner, repo_name, force=True)
        return JsonResponse({"status": "accepted"}, status=202)

    # ── Unknown event ────────────────────────────────────────
    return HttpResponse(status=200)
