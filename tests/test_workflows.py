"""The scheduled jobs publish only through a pull request that passes the required checks (docs/automation.md)."""
import re
import unittest
from pathlib import Path

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows"


class Workflows(unittest.TestCase):
    def test_the_required_check_is_the_tests_job(self):
        t = (WF / "tests.yml").read_text(encoding="utf-8")
        self.assertRegex(t, r"(?m)^jobs:\n  checks:\n", 'the ruleset requires a status named "checks": the job must keep that name')
        self.assertIn("pull_request:", t)

    def test_the_transit_bot_publishes_only_through_a_checked_pull_request(self):
        t = (WF / "refresh-transit.yml").read_text(encoding="utf-8")
        self.assertIn("actions/create-github-app-token@", t)
        self.assertIn("if: vars.BOT_APP_ID != ''", t, "without the App the job must still run (it pushes its branch only)")
        self.assertIn("secrets.BOT_APP_PRIVATE_KEY", t)
        self.assertIn("gh pr merge \"$branch\" --auto --merge", t, "GitHub merges only after the required checks pass")
        self.assertNotIn("gh workflow run pages.yml", t, "publishing before the merge would deploy the old main")
        self.assertNotIn("/statuses/", t, "the bot must not report the required check itself")
        self.assertNotRegex(t, r"(?m)^\s+(statuses|actions): write", "the workflow token needs no more than contents: write")
        order = [t.index(s) for s in ("python -u refresh_network.py", "python check_refresh.py", "node --test", "git push -u origin")]
        self.assertEqual(order, sorted(order), "the data checks and tests run before anything is pushed")

    def test_the_bots_commit_the_ledger_with_the_data(self):
        # refresh_network.py and rebuild.yml run registry.py, which moves the last-updated date of each changed file in dictionary_src/data_ledger.json
        # (docs/data-management.md); a pull request without it would fail python registry.py --check
        for wf in ("refresh-transit.yml", "rebuild.yml"):
            t = (WF / wf).read_text(encoding="utf-8")
            self.assertRegex(t, r"git add site/data[^\n]*dictionary_src/data_ledger\.json", wf)
        self.assertIn("registry.apply()", (WF.parents[1] / "refresh_network.py").read_text(encoding="utf-8"))
        self.assertIn("python registry.py", (WF / "rebuild.yml").read_text(encoding="utf-8"))
        self.assertIn("python registry.py --check", (WF / "tests.yml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
