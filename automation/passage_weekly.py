"""Use the pinned OS release for the weekly bulletin publisher."""
import argparse
import hashlib
import json
import os
import re
import urllib.request
import subprocess
import sys
from pathlib import Path

from bible import save
from bnoc import DEFAULT_CONFIG, advance, config, guard, load, owned, state

SKILL = "bnoc-passage-reader"
VERSION = "1.2.0"
ASSETS = ("og.png", "apple-touch-icon.png", "favicon.svg", "share.json")


def public_bytes(url):
    if sys.platform == "win32":
        curl = Path(os.environ["SystemRoot"]) / "System32" / "curl.exe"
        return subprocess.check_output([str(curl), "--fail", "--silent", "--show-error",
                                        "--location", "--max-time", "30", url])
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def bundle_digest(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + bytes.fromhex(sha(path)))
    return digest.hexdigest()


def profile(configuration):
    pin = configuration["weeklyReader"]
    root = Path(pin["root"])
    if (pin["skill"], pin["version"]) != (SKILL, VERSION) or bundle_digest(root) != pin["sha256"]:
        raise ValueError("Weekly reader release differs from the configured original")
    return root, {key: pin[key] for key in ("skill", "version", "sha256")}


def prepare(configuration, key, token):
    root, pin = profile(configuration)
    folder, run = owned(configuration, key, token)
    if run["mode"] != "publish" or run["service"] != "sunday-morning-adult":
        raise ValueError("A confirmed Sunday morning publishing run is required")
    bulletin = load(folder / "bulletin.json")
    readings = bulletin["observation"]["morningPassages"]
    if readings != [run["reference"]] * 3 or bulletin["observation"]["date"] != run["date"]:
        raise ValueError("The three morning readings and Sunday must agree")
    job = folder / "passage-reader-1.2.0"
    (job / "inputs").mkdir(parents=True, exist_ok=True)
    return root, pin, folder, run, job


def checked_files(job, run, pin, site):
    out = job / "out"
    if load(job/"message.json").get("schemaVersion") != 5 or load(job/"brief.json").get("schemaVersion") != 5:
        raise ValueError("Edition 5 sermon and brief required")
    receipt = load(out / "message-receipt.json")
    share = load(out / "share.json")
    url = site.rstrip("/") + "/" + run["relativePath"]
    if receipt["status"] != "ok" or set(receipt["share"]["files"]) != set(ASSETS) or share["url"] != url:
        raise ValueError("Incomplete render or wrong public URL")
    by_source = {"reading.html":run["relativePath"], **{name:str(Path(run["relativePath"]).parent.as_posix())+"/"+name for name in ASSETS}}
    hashes = {target:sha(out/src) for src,target in by_source.items()}
    checked = [job/"message.json",job/"brief.json",job/"audit.json",*sorted((job/"inputs").glob("*.json"))]
    inputs = hashlib.sha256()
    for path in checked:
        inputs.update(path.relative_to(job).as_posix().encode()+b"\0"+bytes.fromhex(sha(path)))
    return {"id":run["id"], "date":run["date"], "reference":run["reference"], "service":run["service"],
            "relativePath":run["relativePath"], "versions":pin, "publicationStatus":"published",
            "htmlSha256":hashes[run["relativePath"]], "files":hashes,
            "reviewedInputsSha256":inputs.hexdigest(), "auditSha256":sha(job/"audit.json"), "reviewModel":load(job/"audit.json")["reviewer"]}


def render(c, root, pin, folder, run, job):
    out = job / "out"
    if load(job/"message.json").get("schemaVersion") != 5 or load(job/"brief.json").get("schemaVersion") != 5:
        raise ValueError("New sermon and brief must use schema 5")
    passage = load(job/"inputs"/"passage.json")
    # OS canonical book IDs may differ from the existing publisher's slug (e.g. Jonah).
    book_codes = {}
    for line in (root/"references"/"books.tsv").read_text(encoding="utf-8").splitlines():
        code, _, _, _, title, aliases = line.split("\t")
        for alias in [title, *aliases.split(",")]:
            book_codes[alias.strip()] = code
    expected = [f"GAE:{book_codes[book]}.{ch}.{n}" for book,ch,n in run["selected"]]
    if passage["edition"] != "GAE" or [v["id"] for v in passage["verses"]] != expected:
        raise ValueError("Passage packet does not match the confirmed reference")
    base = [sys.executable,"-B","-X","utf8",str(root/"scripts"/"message.py")]
    inputs = ["--brief",job/"brief.json","--passage",job/"inputs"/"passage.json"]
    for evidence in sorted((job/"inputs").glob("*.json")):
        if evidence.name != "passage.json" and "verses" in load(evidence):
            inputs.extend(["--evidence",evidence])
    subprocess.run([sys.executable,"-B","-X","utf8",root/"scripts"/"design.py","check"],check=True)
    subprocess.run([*base,"check-brief",*inputs],check=True)
    subprocess.run([*base,"render",*inputs,"--message",job/"message.json","--audit",job/"audit.json","--out-dir",out,"--url",c["site"].rstrip("/")+"/"+run["relativePath"]],check=True)
    record = checked_files(job,run,pin,c["site"])
    save(job/"publication.json",record)
    run["versions"] = pin
    advance(c,folder,run,"rendered")
    return record


def stage(c, pin, run, job, checkout):
    out = job / "out"
    repo = checkout.resolve()
    record = checked_files(job,run,pin,c["site"])
    if run["stage"] != "rendered" or load(job/"publication.json") != record:
        raise ValueError("A matching verified render is required")
    def git(*args):
        return subprocess.check_output(["git",*args],cwd=repo).decode().strip()
    if Path(git("rev-parse","--show-toplevel")).resolve() != repo:
        raise ValueError("Pass the root of the BNOC checkout")
    if git("remote","get-url","origin").lower().removesuffix(".git") not in ("https://github.com/laguna821/bnoc","git@github.com:laguna821/bnoc"):
        raise ValueError("Unexpected publication repository")
    manifest = repo/"issues"/(run["id"]+".json")
    existing = load(manifest) if manifest.is_file() else None
    if existing and existing != record:
        if not (existing.get("publicationStatus")=="withdrawn-pending-replacement"
                and existing.get("replacementSkill")==SKILL+"@"+VERSION
                and all(existing.get(k)==record[k] for k in ["id","date","relativePath","service","reference"])):
            raise ValueError("Existing issue differs from the reviewed replacement")
    target = repo/run["relativePath"]
    if not target.resolve().is_relative_to(repo) or not target.parent.parent.parent == repo:
        raise ValueError("Unexpected weekly output directory")
    for other in (repo/"issues").glob(run["date"]+"-*.json"):
        if other != manifest and load(other).get("service")==run["service"]:
            raise ValueError("Another issue exists for this date and service")
    outputs={target:out/"reading.html", **{target.parent/n:out/n for n in ASSETS}}
    for dest, source in outputs.items():
        if dest.exists() and sha(dest)!=sha(source):
            raise ValueError("Public asset collision: "+str(dest))
    target.parent.mkdir(parents=True,exist_ok=True)
    for dest, source in outputs.items():
        dest.write_bytes(source.read_bytes())
    save(manifest,record)
    paths=[str(dest.relative_to(repo).as_posix()) for dest in [*outputs,manifest]]
    git("-c","core.autocrlf=false","add","--",*paths)
    for dest in outputs:
        data=subprocess.check_output(["git","show",":"+dest.relative_to(repo).as_posix()],cwd=repo)
        if hashlib.sha256(data).hexdigest()!=record["files"][dest.relative_to(repo).as_posix()]:
            raise ValueError("Git changed published bytes during staging")
    return record


def confirm(c, pin, folder, run, job, commit):
    out = job / "out"
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("confirm requires the deployed commit SHA")
    jobs = json.loads(public_bytes("https://api.github.com/repos/laguna821/BNOC/actions/runs?head_sha="+commit))["workflow_runs"]
    matches = [job for job in jobs if job["name"]=="BNOC Pages (hub+feed)" and job["head_sha"]==commit
               and job["head_branch"]=="main" and job["status"]=="completed" and job["conclusion"]=="success"]
    if not matches:
        raise ValueError("No successful Pages workflow for the supplied commit")
    workflow_url = matches[0]["html_url"]
    record = checked_files(job,run,pin,c["site"])
    if load(job/"publication.json") != record:
        raise ValueError("Rendered publication changed")
    run_id = run["id"]
    manifest_url = f"https://raw.githubusercontent.com/laguna821/BNOC/{commit}/issues/{run_id}.json"
    if json.loads(public_bytes(manifest_url)) != record:
        raise ValueError("Commit does not contain this reviewed publication")
    for path, expected in record["files"].items():
        if hashlib.sha256(public_bytes(c["site"].rstrip("/")+"/"+path)).hexdigest() != expected:
            raise ValueError("Public bytes differ: "+path)
    for name in ("index.json","search.json"):
        items=json.loads(public_bytes(c["site"].rstrip("/")+"/"+name))
        if isinstance(items,dict):
            items=items["items"]
        matches=[x for x in items if x["link"].endswith("/"+run["relativePath"]) and x["date"]==run["date"] and x["title"]==load(out/"share.json")["title"]]
        if len(matches)!=1:
            raise ValueError("Expected one published entry in "+name)
    run["url"]=c["site"].rstrip("/")+"/"+run["relativePath"]
    run["commit"]=run["deploymentCommit"]=commit
    run["deploymentWorkflow"]=workflow_url
    run["lease"]=None
    advance(c,folder,run,"published")
    current=state(c)
    current["issues"][run["id"]].update(url=run["url"],commit=commit)
    save(c["root"]/"state.json",current)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("action", choices=["profile","prepare","render","stage","confirm"])
    parser.add_argument("--run-id")
    parser.add_argument("--token")
    parser.add_argument("--checkout",type=Path)
    parser.add_argument("--commit",help="Deployed main commit for confirm")
    args = parser.parse_args()
    c = config(args.config)
    if args.action == "profile":
        print(json.dumps(profile(c)[1]))
        return
    with guard(c["root"]):
        root,pin,folder,run,job = prepare(c,args.run_id,args.token)
        if args.action == "prepare":
            print(json.dumps({"job":str(job),"skillRoot":str(root),"reference":run["reference"],"relativePath":run["relativePath"]},ensure_ascii=False))
            return
        if args.action == "render":
            record = render(c,root,pin,folder,run,job)
        elif args.action == "stage":
            if args.checkout is None:
                parser.error("stage requires --checkout")
            record = stage(c,pin,run,job,args.checkout)
        else:
            record = confirm(c,pin,folder,run,job,args.commit or "")
        print(json.dumps(record,ensure_ascii=False))


if __name__ == "__main__":
    main()
