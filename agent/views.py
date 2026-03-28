import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .repo_reader import read_repo
from .repo_understander import understand_repo

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def webhook(request):
    res = HttpResponse(status=200)

    event = request.headers.get("X-GitHub-Event", "")
    if event != "push":
        return res

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    ref = payload.get("ref", "")
    if ref not in ("refs/heads/main", "refs/heads/master"):
        return res

    owner = payload["repository"]["owner"]["login"]
    repo = payload["repository"]["name"]
    installation_id = payload["installation"]["id"]

    logger.info(f"\n🚀 Push on {owner}/{repo} — starting LynX agent")

    try:
        # Step 1 — Read the full repo
        repo_data = read_repo(installation_id, owner, repo)
        logger.info(f"\n📁 File Tree:\n{repo_data['tree_visual']}")

        # Step 2 — Understand the repo (Claude)
        understanding = understand_repo(repo_data)
        logger.info(f"\n🧠 Understanding:\n{json.dumps(understanding, indent=2)}")

        # Step 3 — (Hours 5-7) Pass to YAML generator here
        # generate_and_pr(repo_data, understanding, installation_id, owner, repo)

    except Exception as e:
        logger.error(f"❌ Agent failed: {e}", exc_info=True)

    return res
