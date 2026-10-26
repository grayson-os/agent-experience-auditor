"""Tests for the Architecture Canvas renderer.

Run from the repository root:
    python3 -m unittest discover -s tests
"""

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.dom.minidom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "os11-audit-architecture", "scripts", "render_canvas.py")
EXAMPLE = os.path.join(ROOT, "skills", "os11-audit-architecture", "assets", "example-canvas.json")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")

sys.path.insert(0, os.path.dirname(SCRIPT))
import render_canvas  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def module(name, layer, sublayer, **extra):
    return dict(name=name, layer=layer, sublayer=sublayer, references_checked=True, **extra)


def refs(*pairs):
    return [{"from": a, "to": b} for a, b in pairs]


def edges(analysis, kind):
    return {(v["from"], v["to"]) for v in analysis["violations"] if kind in v["kinds"]}


class IndirectCycleTest(unittest.TestCase):
    def setUp(self):
        self.model = load(os.path.join(FIXTURES, "indirect-cycle.json"))
        self.analysis = render_canvas.analyze(self.model)

    def test_flags_every_reference_in_the_indirect_cycle(self):
        self.assertEqual(edges(self.analysis, "cycle"), {
            ("Claims_BL", "Policy_BL"), ("Policy_BL", "Policy_CS"),
            ("Claims_BL", "Claims_CS"), ("Claims_CS", "Policy_CS"),
            ("Policy_CS", "Claims_BL"),
        })

    def test_groups_the_cycle_and_lists_its_paths(self):
        self.assertEqual(len(self.analysis["cycles"]), 1)
        cycle = self.analysis["cycles"][0]
        self.assertEqual(cycle["id"], "C1")
        self.assertEqual(cycle["members"], ["Claims_BL", "Claims_CS", "Policy_BL", "Policy_CS"])
        self.assertEqual(cycle["paths"], [
            ("Claims_BL", "Claims_CS", "Policy_CS"),
            ("Claims_BL", "Policy_BL", "Policy_CS"),
        ])
        self.assertEqual(render_canvas.cycle_kind(cycle), "indirect")

    def test_names_the_reference_against_sub_layer_order(self):
        self.assertEqual(self.analysis["cycles"][0]["break_candidates"], [("Policy_CS", "Claims_BL")])

    def test_core_side_references_outside_a_cycle_are_allowed(self):
        flagged = {(v["from"], v["to"]) for v in self.analysis["violations"]}
        self.assertNotIn(("Claims_CS", "Customer_CS"), flagged)

    def test_platform_modules_are_not_judged(self):
        # Common_Lib -> Users is upward and judged; OutSystemsUI -> Users is not.
        self.assertEqual(edges(self.analysis, "upward"), {("Common_Lib", "Users")})

    def test_reports_modules_whose_references_were_not_checked(self):
        # The audited module counts as checked; platform modules are never listed.
        self.assertEqual(self.analysis["unchecked"], ["Customer_CS"])


class RulesTest(unittest.TestCase):
    def analyze(self, modules, references):
        return render_canvas.analyze({"modules": modules, "references": references})

    def test_direct_cycle(self):
        analysis = self.analyze(
            [module("A_BL", "core", "Composite Logic"), module("B_BL", "core", "Composite Logic")],
            refs(("A_BL", "B_BL"), ("B_BL", "A_BL")),
        )
        self.assertEqual(edges(analysis, "cycle"), {("A_BL", "B_BL"), ("B_BL", "A_BL")})
        self.assertEqual(render_canvas.cycle_kind(analysis["cycles"][0]), "direct")

    def test_long_indirect_cycle_across_layers(self):
        names = ["A_UI", "B_BL", "C_CS", "D_Lib"]
        layers = [("end-user", "End User"), ("core", "Composite Logic"), ("core", "Core Service"), ("foundation", "Library")]
        analysis = self.analyze(
            [module(n, *l) for n, l in zip(names, layers)],
            refs(("A_UI", "B_BL"), ("B_BL", "C_CS"), ("C_CS", "D_Lib"), ("D_Lib", "A_UI")),
        )
        self.assertEqual(len(edges(analysis, "cycle")), 4)
        self.assertEqual(analysis["cycles"][0]["paths"], [("A_UI", "B_BL", "C_CS", "D_Lib")])
        self.assertEqual(edges(analysis, "upward"), {("D_Lib", "A_UI")})

    def test_core_sub_layer_reference_without_cycle_is_allowed(self):
        analysis = self.analyze(
            [module("A_CS", "core", "Core Service"), module("B_BL", "core", "Composite Logic")],
            refs(("A_CS", "B_BL")),
        )
        self.assertEqual(analysis["violations"], [])

    def test_side_reference_at_end_user(self):
        analysis = self.analyze(
            [module("A_UI", "end-user", "End User"), module("B_UI", "end-user", "End User")],
            refs(("A_UI", "B_UI")),
        )
        self.assertEqual(edges(analysis, "side"), {("A_UI", "B_UI")})

    def test_separate_cycles_get_separate_ids(self):
        analysis = self.analyze(
            [module(n, "core", "Core Service") for n in ("A_CS", "B_CS", "C_CS", "D_CS")],
            refs(("A_CS", "B_CS"), ("B_CS", "A_CS"), ("C_CS", "D_CS"), ("D_CS", "C_CS")),
        )
        self.assertEqual([c["id"] for c in analysis["cycles"]], ["C1", "C2"])
        self.assertEqual([c["members"] for c in analysis["cycles"]], [["A_CS", "B_CS"], ["C_CS", "D_CS"]])

    def test_deep_chain_does_not_hit_the_recursion_limit(self):
        count = 3000
        names = ["M{}_CS".format(i) for i in range(count)]
        analysis = self.analyze(
            [module(n, "core", "Core Service") for n in names],
            refs(*[(names[i], names[(i + 1) % count]) for i in range(count)]),
        )
        self.assertEqual(len(analysis["cycles"]), 1)
        self.assertEqual(len(edges(analysis, "cycle")), count)


class FocusTest(unittest.TestCase):
    def test_small_models_get_no_focused_diagram(self):
        model = load(EXAMPLE)
        self.assertIsNone(render_canvas.focus_modules(model, render_canvas.analyze(model)))

    def test_large_models_keep_audited_neighbours_and_violations(self):
        modules = [module("App_UI", "end-user", "End User")]
        modules += [module("Svc{}_CS".format(i), "core", "Core Service") for i in range(20)]
        modules += [module("Util_Lib", "foundation", "Library")]
        references = refs(("App_UI", "Svc0_CS"), ("Util_Lib", "Svc5_CS"), ("Svc7_CS", "Svc8_CS"), ("Svc8_CS", "Svc7_CS"))
        model = {"audited": "App_UI", "modules": modules, "references": references}
        keep = render_canvas.focus_modules(model, render_canvas.analyze(model))
        self.assertEqual(keep, {"App_UI", "Svc0_CS", "Util_Lib", "Svc5_CS", "Svc7_CS", "Svc8_CS"})


class CommandLineTest(unittest.TestCase):
    def run_script(self, model):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "canvas.json")
            target = os.path.join(tmp, "canvas.svg")
            with open(source, "w", encoding="utf-8") as handle:
                json.dump(model, handle)
            result = subprocess.run([sys.executable, SCRIPT, source, target], capture_output=True, text=True)
            svgs = {}
            for name in os.listdir(tmp):
                if name.endswith(".svg"):
                    with open(os.path.join(tmp, name), encoding="utf-8") as handle:
                        svgs[name] = handle.read()
            return result, svgs

    def test_renders_valid_svg_and_summary(self):
        result, svgs = self.run_script(load(os.path.join(FIXTURES, "indirect-cycle.json")))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(svgs), {"canvas.svg"})
        xml.dom.minidom.parseString(svgs["canvas.svg"])
        self.assertIn("C1 (indirect, 4 modules)", result.stdout)
        self.assertIn("Claims_BL -> Claims_CS -> Policy_CS -> Claims_BL", result.stdout)
        self.assertIn("Against the canvas order: Policy_CS -> Claims_BL", result.stdout)
        self.assertIn("References not checked for: Customer_CS", result.stdout)

    def test_example_renders(self):
        result, svgs = self.run_script(load(EXAMPLE))
        self.assertEqual(result.returncode, 0, result.stderr)
        xml.dom.minidom.parseString(svgs["canvas.svg"])

    def test_large_model_writes_focused_diagram(self):
        modules = [module("App_UI", "end-user", "End User")]
        modules += [module("Svc{}_CS".format(i), "core", "Core Service") for i in range(20)]
        model = {"audited": "App_UI", "modules": modules, "references": refs(("App_UI", "Svc0_CS"))}
        result, svgs = self.run_script(model)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(svgs), {"canvas.svg", "canvas-focus.svg"})
        xml.dom.minidom.parseString(svgs["canvas-focus.svg"])
        self.assertIn("Focused view: 2 of 21 modules", svgs["canvas-focus.svg"])

    def test_rejects_invalid_models(self):
        good = load(os.path.join(FIXTURES, "indirect-cycle.json"))
        cases = {
            "unknown sublayer": lambda m: m["modules"][0].update(sublayer="Orchestration"),
            "unknown owner": lambda m: m["modules"][0].update(owner="forge"),
            "undeclared module": lambda m: m["references"].append({"from": "Claims_UI", "to": "Nope"}),
            "duplicate reference": lambda m: m["references"].append(dict(m["references"][0])),
            "non-boolean flag": lambda m: m["modules"][1].update(references_checked="yes"),
        }
        for label, change in cases.items():
            with self.subTest(label):
                model = copy.deepcopy(good)
                change(model)
                result, _ = self.run_script(model)
                self.assertEqual(result.returncode, 1)
                self.assertTrue(result.stderr.startswith("error: "), result.stderr)


if __name__ == "__main__":
    unittest.main()
