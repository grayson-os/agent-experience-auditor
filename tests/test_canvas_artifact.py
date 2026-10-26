"""Tests for the interactive Architecture Canvas Artifact template.

The template computes violations and cycles in JavaScript. These tests run that
code under Node and check that it agrees with render_canvas.py on the example,
the fixtures, invalid models, and a few hundred random models.

Run from the repository root:
    python3 -m unittest discover -s tests
"""

import contextlib
import copy
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "os11-audit-architecture")
SCRIPT = os.path.join(SKILL, "scripts", "render_canvas.py")
TEMPLATE = os.path.join(SKILL, "assets", "canvas-artifact.html")
EXAMPLE = os.path.join(SKILL, "assets", "example-canvas.json")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")

sys.path.insert(0, os.path.dirname(SCRIPT))
import render_canvas  # noqa: E402

NODE = shutil.which("node")

HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8") + "\nthis.CANVAS = CANVAS;", context);
const CANVAS = context.CANVAS;
const models = JSON.parse(fs.readFileSync(0, "utf8"));
const results = models.map((model) => {
  try {
    CANVAS.validate(model);
  } catch (err) {
    if (err instanceof CANVAS.CanvasError) return { error: err.message };
    throw err;
  }
  const analysis = CANVAS.analyze(model);
  return {
    analysis,
    kinds: analysis.cycles.map((c) => CANVAS.cycleKind(c)),
    labels: analysis.violations.map((v) => CANVAS.violationLabel(v)),
    focus: CANVAS.focusModules(model, analysis),
  };
});
process.stdout.write(JSON.stringify(results));
"""


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def analysis_block():
    with open(TEMPLATE, encoding="utf-8") as handle:
        html = handle.read()
    match = re.search(r"// BEGIN CANVAS ANALYSIS\n(.*?)// END CANVAS ANALYSIS", html, re.S)
    if not match:
        raise AssertionError("the template has no CANVAS ANALYSIS block")
    return match.group(1)


def python_result(model):
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            render_canvas.validate(model)
    except SystemExit:
        return {"error": stderr.getvalue().strip()[len("error: "):]}
    analysis = render_canvas.analyze(model)
    keep = render_canvas.focus_modules(model, analysis)
    return json.loads(json.dumps({
        "analysis": analysis,
        "kinds": [render_canvas.cycle_kind(c) for c in analysis["cycles"]],
        "labels": [render_canvas.violation_label(v) for v in analysis["violations"]],
        "focus": sorted(keep, key=str.lower) if keep else None,
    }))


def random_model(rng):
    layers = [(layer["id"], sub) for layer in render_canvas.LAYERS for sub in layer["sublayers"]]
    count = rng.randint(2, 24)
    modules = []
    for i in range(count):
        layer, sublayer = rng.choice(layers)
        module = {"name": "{}{}_{}".format(rng.choice("ABCDEFGH"), i, rng.choice(["X", "y"])), "layer": layer, "sublayer": sublayer}
        if rng.random() < 0.15:
            module["owner"] = "platform"
        if rng.random() < 0.7:
            module["references_checked"] = rng.random() < 0.85
        modules.append(module)
    names = [m["name"] for m in modules]
    pairs = {(a, b) for a in names for b in names if a != b and rng.random() < 2.2 / count}
    model = {"modules": modules, "references": [{"from": a, "to": b} for a, b in sorted(pairs)]}
    if rng.random() < 0.8:
        model["audited"] = rng.choice(names)
    return model


@unittest.skipUnless(NODE, "Node.js is not installed")
class AnalysisParityTest(unittest.TestCase):
    def compare(self, models):
        with tempfile.TemporaryDirectory() as tmp:
            block = os.path.join(tmp, "analysis.js")
            harness = os.path.join(tmp, "harness.js")
            with open(block, "w", encoding="utf-8") as handle:
                handle.write(analysis_block())
            with open(harness, "w", encoding="utf-8") as handle:
                handle.write(HARNESS)
            result = subprocess.run([NODE, harness, block], input=json.dumps(models),
                                    capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        for i, (model, js) in enumerate(zip(models, json.loads(result.stdout))):
            with self.subTest(model=i):
                self.assertEqual(js, python_result(model))

    def test_example_and_fixtures(self):
        models = [load(EXAMPLE)]
        for name in sorted(os.listdir(FIXTURES)):
            if name.endswith(".json"):
                models.append(load(os.path.join(FIXTURES, name)))
        self.compare(models)

    def test_invalid_models_give_the_same_error(self):
        good = load(os.path.join(FIXTURES, "indirect-cycle.json"))
        changes = [
            lambda m: m["modules"][0].update(sublayer="Orchestration"),
            lambda m: m["modules"][0].update(layer="orchestration"),
            lambda m: m["modules"][0].update(owner="forge"),
            lambda m: m["modules"][1].update(references_checked="yes"),
            lambda m: m["modules"].append(dict(m["modules"][0])),
            lambda m: m["modules"][0].pop("name"),
            lambda m: m["references"].append({"from": "Claims_UI", "to": "Nope"}),
            lambda m: m["references"].append({"from": "Claims_UI", "to": "Claims_UI"}),
            lambda m: m["references"].append(dict(m["references"][0])),
            lambda m: m.update(audited="Nope"),
            lambda m: m.update(omitted="Nope"),
            lambda m: m.update(modules=[]),
            lambda m: m.update(references={}),
        ]
        models = []
        for change in changes:
            model = copy.deepcopy(good)
            change(model)
            models.append(model)
        models.append([])
        self.compare(models)

    def test_random_models(self):
        rng = random.Random(11)
        self.compare([random_model(rng) for _ in range(300)])


class HtmlOutputTest(unittest.TestCase):
    def run_script(self, model):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "canvas.json")
            with open(source, "w", encoding="utf-8") as handle:
                json.dump(model, handle)
            target = os.path.join(tmp, "canvas.html")
            result = subprocess.run([sys.executable, SCRIPT, source, os.path.join(tmp, "canvas.svg"), "--html", target],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(target, encoding="utf-8") as handle:
                return result, handle.read()

    def embedded(self, html):
        match = re.search(r'<script type="application/json" id="canvas-model">(.*?)</script>', html, re.S)
        self.assertIsNotNone(match)
        return json.loads(match.group(1))

    def test_embeds_the_model_and_title(self):
        model = load(EXAMPLE)
        result, html = self.run_script(model)
        self.assertNotIn("__CANVAS_MODEL__", html)
        self.assertEqual(self.embedded(html), model)
        self.assertIn("<title>Architecture Canvas: Orders_UI</title>", html)
        self.assertIn("canvas.html", result.stdout)

    def test_model_text_cannot_close_the_script(self):
        model = load(EXAMPLE)
        model["title"] = "</script><b>& co"
        _, html = self.run_script(model)
        self.assertEqual(html.count("</script>"), 3)
        self.assertEqual(self.embedded(html)["title"], "</script><b>& co")
        self.assertIn("<title>&lt;/script&gt;&lt;b&gt;&amp; co</title>", html)

    def test_template_has_one_placeholder(self):
        with open(TEMPLATE, encoding="utf-8") as handle:
            self.assertEqual(handle.read().count("__CANVAS_MODEL__"), 1)


if __name__ == "__main__":
    unittest.main()
