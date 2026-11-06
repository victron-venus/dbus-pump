"""Documentation-only pull requests retain their actual documentation tests."""

import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow(name):
    """Read scalars without interpreting workflow expressions or on as YAML booleans."""
    return yaml.load(  # nosec B506 - BaseLoader constructs only strings, lists and maps.
        (ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader
    )


class DocumentationScopeTests(unittest.TestCase):
    """The required gate and full-release path must preserve documentation validation."""

    def test_documentation_workflow_is_always_required(self):
        """A documentation-only decision cannot skip real link and artifact checks."""
        policy = json.loads((ROOT / ".release-policy.json").read_text())
        self.assertIn("docs.yml", policy["validation_workflows"])
        self.assertIn("docs.yml", policy["change_scope"]["always_validate_workflows"])
        jobs = workflow("quality-gate.yml")["jobs"]
        name = next(
            key for key, job in jobs.items() if job.get("uses") == "./.github/workflows/docs.yml"
        )
        self.assertNotIn("if", jobs[name])
        self.assertIn(name, jobs["gate"]["needs"])
        always = jobs["gate"]["steps"][-1]["run"].split("always = ", 1)[1].splitlines()[0]
        self.assertIn(repr(name), always)

    def test_documentation_job_runs_retained_suite_without_application_install(self):
        """Documentation validation needs only the hash-pinned pytest closure."""
        job = workflow("docs.yml")["jobs"]["documentation"]
        self.assertNotIn("if", job)
        commands = [step["run"] for step in job["steps"] if "run" in step]
        self.assertEqual(
            commands,
            [
                "python -m pip install --require-hashes --only-binary=:all: "
                "-r .github/requirements-docs.txt",
                "python -m pytest -o addopts='' tests/test_docs.py",
            ],
        )

    def test_release_qualification_remains_full(self):
        """A documentation successor still qualifies to replace an automatic release."""
        jobs = workflow("release-pipeline.yml")["jobs"]
        step = next(step for step in jobs["scope"]["steps"] if step.get("id") == "scope")
        self.assertEqual(step["env"]["FORCE_FULL"], "true")
