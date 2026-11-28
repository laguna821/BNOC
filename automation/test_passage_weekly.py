import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bible import save
from bnoc import make_run
from bulletin import validate_observation
from passage_weekly import SKILL, VERSION, bundle_digest, profile


class WeeklyReaderTests(unittest.TestCase):
    def test_profile_detects_asset_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            asset = root / "message.css"
            asset.write_text("original")
            config = {"weeklyReader": {"root":folder,"skill":SKILL,"version":VERSION,"sha256":bundle_digest(root)}}
            self.assertEqual(profile(config)[0],root)
            asset.write_text("replaced")
            with self.assertRaises(ValueError):
                profile(config)

    def test_same_published_issue_and_next_sunday(self):
        with tempfile.TemporaryDirectory() as folder, patch("bnoc.Bible") as bible:
            root = Path(folder)
            config = {"root":root,"bible":"unused"}
            bible.return_value.parse.return_value = [["눅",11,5]]
            service = "sunday-morning-adult"
            run = make_run(config,"눅 11:5","2026-11-29",service,"publish")
            state = json.loads((root/"state.json").read_text(encoding="utf-8"))
            state["issues"][run["runId"]]["stage"]="published"
            save(root/"state.json",state)
            self.assertEqual(make_run(config,"눅 11:5","2026-11-29",service,"publish")["status"],"already-published")
            self.assertEqual(make_run(config,"눅 11:5","2026-12-06",service,"publish")["status"],"created")

    def test_unclear_or_disagreeing_services(self):
        candidate={"date":"2026-12-06","images":["source"]}
        observation={"date":candidate["date"],"service":"sunday-morning-adult","passage":"눅 11:5",
                     "unambiguous":True,"visuallyConfirmed":True,"imageUrl":"source","evidence":"image",
                     "morningPassages":["눅 11:5","눅 11:5","다른 본문"]}
        with self.assertRaises(ValueError):
            validate_observation(candidate,observation)
        observation["unambiguous"]=False
        with self.assertRaises(ValueError):
            validate_observation(candidate,observation)
