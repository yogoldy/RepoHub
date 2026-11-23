import unittest
from tools.report_labels import labels_for

class ReportLabelTests(unittest.TestCase):
    def event(self,kind='bug'):
        return {'action':'opened','repository':{'full_name':'yogoldy/RepoHub'},'issue':{'number':3,'title':'[Bug] Example' if kind=='bug' else '[Feature] Example','body':'Prose\n\nReport ID: '+'a'*24+'\n\nReport type: '+kind}}
    def test_fixed_bug_and_feature_queues(self):
        self.assertEqual(labels_for(self.event()),['bug','from-app'])
        self.assertEqual(labels_for(self.event('feature')),['enhancement','from-app'])
    def test_issue_text_never_selects_other_labels_or_commands(self):
        for field,value in [('body','$(danger)\nReport type: enhancement'),('title','Other title'),('number','3;command')]:
            event=self.event();event['issue'][field]=value;self.assertIsNone(labels_for(event))
        event=self.event();event['repository']['full_name']='evil/other';self.assertIsNone(labels_for(event))
        event=self.event();event['issue']['pull_request']={};self.assertIsNone(labels_for(event))
        event=self.event();event['action']='edited';self.assertIsNone(labels_for(event))
