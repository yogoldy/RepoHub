import copy
from pathlib import Path
import tempfile
import unittest
from tools.release_gate import validate_register,assess_rules,packaging_contract,ROOT

class ReleaseGateTests(unittest.TestCase):
    def rule(self):
        return {'id':'GR01','title':'Example','breakpoint':'Boundary','cause_and_solution':'Cause','required_behavior':'Rule','remaining_gap':'Manual gap','diagnostic_events':['repo_checked'],'test_ids':['test_example.Case.test_example']}
    def test_missing_skipped_failed_or_expected_failure_is_not_a_pass(self):
        rule=self.rule();name=rule['test_ids'][0]
        for value in [None,'skipped','failed','error','expected_failure','unexpected_success']:
            self.assertEqual(assess_rules([rule],{name:value})[0]['result'],'failed')
        self.assertEqual(assess_rules([rule],{name:'passed'})[0]['result'],'passed')
    def test_register_rejects_empty_duplicate_and_invalid_test_contract(self):
        rule=self.rule()
        for value in [{'schema_version':1,'rules':[]},{'schema_version':1,'rules':[rule,rule]},{'schema_version':2,'rules':[rule]}]:
            with self.assertRaises(ValueError):validate_register(value)
        bad=copy.deepcopy(rule);bad['test_ids']=['not-an-executed-test']
        with self.assertRaises(ValueError):validate_register({'schema_version':1,'rules':[bad]})
        bad=copy.deepcopy(rule);bad['diagnostic_events']=['unregistered_event']
        with self.assertRaises(ValueError):validate_register({'schema_version':1,'rules':[bad]})
    def test_current_installer_and_html_dependencies_are_packaged(self):
        self.assertGreaterEqual(packaging_contract(ROOT)['runtime_modules'],10)
    def test_new_runtime_import_does_not_silently_escape_package_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'install.py').write_text("for name in ('repohub.py',): pass\n")
            (root/'repohub.py').write_text('import new_module\nroutes={}\n')
            (root/'new_module.py').write_text('')
            with self.assertRaisesRegex(ValueError,'Unpackaged'):packaging_contract(root)
