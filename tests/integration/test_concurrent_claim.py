#!/usr/bin/env python3
"""tests/integration/test_concurrent_claim.py
Integration tests for concurrent scene claim / locking.
"""

import multiprocessing
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "bin"))

from checks._utils import claim_scene, release_scene_claim

TMP_DIR = os.path.join(PROJECT_ROOT, ".agent", "tmp")


def _claim_worker(scene_name: str, agent_id: str, result_queue):
    """Worker process that attempts to claim a scene."""
    result = claim_scene(scene_name, agent_id)
    result_queue.put({"agent_id": agent_id, "result": result})


class TestConcurrentClaim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.chdir(PROJECT_ROOT)
        os.makedirs(TMP_DIR, exist_ok=True)

    def tearDown(self):
        # Clean up all claim files under .agent/tmp/
        for entry in os.listdir(TMP_DIR):
            claim_path = os.path.join(TMP_DIR, entry, ".claimed_by")
            lock_path = claim_path + ".lock"
            if os.path.isfile(claim_path):
                os.remove(claim_path)
            if os.path.isfile(lock_path):
                os.remove(lock_path)

    def test_concurrent_claim_same_scene(self):
        """Two agents claim the same scene simultaneously: only one succeeds."""
        scene_name = "test_concurrent_scene"
        os.makedirs(os.path.join(TMP_DIR, scene_name), exist_ok=True)

        q = multiprocessing.Queue()
        p1 = multiprocessing.Process(target=_claim_worker, args=(scene_name, "agent-A", q))
        p2 = multiprocessing.Process(target=_claim_worker, args=(scene_name, "agent-B", q))

        p1.start()
        p2.start()
        p1.join()
        p2.join()

        results = [q.get(timeout=5), q.get(timeout=5)]
        ok_results = [r for r in results if r["result"]["ok"]]
        fail_results = [r for r in results if not r["result"]["ok"]]

        self.assertEqual(len(ok_results), 1, f"Expected exactly 1 success, got {len(ok_results)}")
        self.assertEqual(len(fail_results), 1, f"Expected exactly 1 failure, got {len(fail_results)}")

        # Verify the failure is due to existing claim
        self.assertIn("owner", fail_results[0]["result"])

    def test_concurrent_claim_different_scenes(self):
        """Two agents claim different scenes simultaneously: both succeed."""
        scene_a = "test_scene_a"
        scene_b = "test_scene_b"
        os.makedirs(os.path.join(TMP_DIR, scene_a), exist_ok=True)
        os.makedirs(os.path.join(TMP_DIR, scene_b), exist_ok=True)

        q = multiprocessing.Queue()
        p1 = multiprocessing.Process(target=_claim_worker, args=(scene_a, "agent-A", q))
        p2 = multiprocessing.Process(target=_claim_worker, args=(scene_b, "agent-B", q))

        p1.start()
        p2.start()
        p1.join()
        p2.join()

        results = [q.get(timeout=5), q.get(timeout=5)]
        ok_results = [r for r in results if r["result"]["ok"]]

        self.assertEqual(len(ok_results), 2, f"Expected 2 successes, got {len(ok_results)}")

    def test_claim_expires_and_can_reclaim(self):
        """After releasing a claim, another agent can claim the scene."""
        scene_name = "test_reclaim_scene"
        os.makedirs(os.path.join(TMP_DIR, scene_name), exist_ok=True)

        r1 = claim_scene(scene_name, "agent-A")
        self.assertTrue(r1["ok"])

        release_scene_claim(scene_name)

        r2 = claim_scene(scene_name, "agent-B")
        self.assertTrue(r2["ok"])

    def test_check_report_lock_no_clobber(self):
        """Two processes writing check reports concurrently should not lose data."""
        from checks._utils import read_check_report, write_check_report

        report_path = os.path.join(PROJECT_ROOT, ".agent", "check_reports", "test_concurrent.json")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)

        def writer(agent_id, issues):
            data = {"agent_id": agent_id, "issues": issues}
            write_check_report(report_path, data)

        # Start two writers simultaneously
        p1 = multiprocessing.Process(target=writer, args=("agent-A", [{"type": "A"}]))
        p2 = multiprocessing.Process(target=writer, args=("agent-B", [{"type": "B"}]))
        p1.start()
        p2.start()
        p1.join()
        p2.join()

        # The report should contain valid JSON from one of the writers
        data = read_check_report(report_path)
        self.assertIn("agent_id", data)
        self.assertIn("issues", data)
        # Either A or B should have won, but not mixed/corrupt JSON
        self.assertIn(data["agent_id"], ["agent-A", "agent-B"])

        # Cleanup
        os.remove(report_path)
        lock_path = report_path + ".lock"
        if os.path.isfile(lock_path):
            os.remove(lock_path)


if __name__ == "__main__":
    unittest.main()
