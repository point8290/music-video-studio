"""Export one finished project as a static showcase (for a portfolio page).

Talks to your locally running backend, then writes:
  <out>/showcase.json         project, lyrics, characters and scenes
  <out>/final.mp4             the rendered video (if rendered)
  <out>/keyframes/scene-N.png one keyframe per scene (if generated)

Usage (with the backend running on http://localhost:8000):
  python scripts/export_showcase.py --list
  python scripts/export_showcase.py --project <project-id> --out ../mvs-showcase

Only the Python standard library is used. You'll be asked for the e-mail and
password of your local account; they are sent only to --api.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def call(api: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{api}{path}", data=data, method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=120) as res:
        return res.read()


def get_json(api: str, path: str, token: str):
    try:
        return json.loads(call(api, path, token))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def download(api: str, path: str, token: str, dest: Path) -> bool:
    try:
        content = call(api, path, token)
    except urllib.error.HTTPError as err:
        print(f"  skipped {path} ({err.code})")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    print(f"  saved {dest} ({len(content) // 1024} KB)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--project", help="project id to export")
    parser.add_argument("--out", default="mvs-showcase")
    parser.add_argument("--list", action="store_true", help="list your projects and exit")
    args = parser.parse_args()
    api = args.api.rstrip("/")

    email = input("Local account e-mail: ").strip()
    password = getpass.getpass("Local account password: ")
    auth = json.loads(call(api, "/auth/login", body={"email": email, "password": password}))
    token = auth.get("accessToken") or auth.get("access_token")

    if args.list or not args.project:
        for p in json.loads(call(api, "/projects", token)):
            print(f"{p['id']}  {p['status']:<12}  {p['title']}")
        return 0

    pid = args.project
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    project = get_json(api, f"/projects/{pid}", token)
    lyrics = get_json(api, f"/projects/{pid}/lyrics", token)
    characters = get_json(api, f"/projects/{pid}/characters", token) or []
    scenes = get_json(api, f"/projects/{pid}/scenes", token) or []

    print(f"Exporting '{project['title']}' ({len(scenes)} scenes)")
    for scene in scenes:
        n = scene["number"]
        scene["keyframeFile"] = None
        if scene.get("keyframePath") and download(api, f"/scenes/{scene['id']}/keyframe/file", token, out / "keyframes" / f"scene-{n}.png"):
            scene["keyframeFile"] = f"keyframes/scene-{n}.png"
        for key in ("keyframePath", "clipPath"):  # local disk paths are not useful publicly
            scene.pop(key, None)
    for c in characters:
        c.pop("refImagePath", None)
        c.pop("loraPath", None)

    has_video = download(api, f"/projects/{pid}/render/file", token, out / "final.mp4")

    showcase = {
        "project": project,
        "lyrics": lyrics,
        "characters": characters,
        "scenes": scenes,
        "video": "final.mp4" if has_video else None,
    }
    (out / "showcase.json").write_text(json.dumps(showcase, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Done: {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
