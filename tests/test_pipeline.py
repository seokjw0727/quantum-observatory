import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from argparse import Namespace

from pipeline.model import make_record,merge_records,group_works,doi_id,arxiv_id,day,week_start,validate,clean
from pipeline.adapters import parse_arxiv,parse_crossref,parse_qip,parse_gao,parse_osti
from pipeline.aggregate import aggregate
from pipeline.collect import collect,save_records,read_records

NOW='2026-09-07T00:17:00+00:00'


def paper(source='arxiv',sid='2609.00001',**kw):
    defaults=dict(published_at='2026-09-01T10:00:00Z',arxiv_id=sid if source=='arxiv' else None)
    defaults.update(kw)
    return make_record(source,sid,'Quantum error correction for logical qubits','preprint' if source=='arxiv' else 'journal_article','https://example.org/'+sid,NOW,**defaults)


class DataIntegrity(unittest.TestCase):
    def test_cleaning_preserves_mathematical_inequalities(self):
        self.assertEqual(clean('$a < b$ and $c > d$'),'$a < b$ and $c > d$')
        self.assertEqual(clean('An <i>entangled</i> state'),'An entangled state')

    def test_identifier_normalization(self):
        self.assertEqual(doi_id('https://doi.org/10.1103/ABC'),'10.1103/abc')
        self.assertEqual(arxiv_id('https://arxiv.org/abs/2609.00001v3'),'2609.00001')
        self.assertIsNone(doi_id('javascript:alert(1)'))

    def test_korea_week_boundary_and_date_only(self):
        self.assertEqual(week_start('2026-09-06T15:00:00Z'),date(2026,9,7))
        self.assertEqual(week_start('2026-09-06T14:59:59Z'),date(2026,8,31))
        self.assertEqual(day('2026-09-06'),date(2026,9,6))

    def test_revision_preserves_first_seen_and_is_idempotent(self):
        old=paper();new=dict(old,observed_at='2026-09-08T00:00:00Z',version=2,events=[{'type':'revision','date':NOW,'version':2}])
        once=merge_records([old],[new]);twice=merge_records(once,[new])
        self.assertEqual(once,twice);self.assertEqual(once[0]['observed_at'],NOW);self.assertEqual(len(once[0]['events']),1)

    def test_preprint_and_journal_are_one_work(self):
        a=paper(doi='10.1103/test');b=paper('crossref','10.1103/test',doi='10.1103/test',published_at='2026-09-03')
        groups=group_works([a,b]);self.assertEqual(len(groups),1);self.assertEqual(groups[0]['first_published'],a['published_at'])

    def test_matching_titles_are_not_silently_merged(self):
        self.assertEqual(len(group_works([paper(sid='2609.00001'),paper(sid='2609.00002')])),2)

    def test_talk_does_not_shift_research_publication_date(self):
        a=paper(doi='10.1103/test');t=make_record('qip','one',a['title'],'talk','https://example.org/talk',NOW,doi='10.1103/test',published_at='2025-01-01',event_start='2026-01-26')
        self.assertEqual(group_works([a,t])[0]['first_published'],a['published_at'])

    def test_unsafe_url_rejected(self):
        with self.assertRaises(ValueError):make_record('x','y','Quantum','report','javascript:alert(1)',NOW)

    def state(self,failed=False):
        return dict(run_id='test',last_success=NOW,sources={sid:dict(status='failed' if failed and sid=='arxiv' else 'success',covered_from='2026-06-01') for sid in ['arxiv','crossref']})

    def test_counts_match_linked_research_and_undated_reports(self):
        a=paper(doi='10.1103/test');b=paper('crossref','10.1103/test',doi='10.1103/test')
        r=make_record('reports','one','Quantum report','report','https://example.org/report',NOW,date_precision='unknown')
        result=aggregate([a,b,r],self.state());w=next(w for w in result['weeks'] if w['id']=='2026-08-31')
        self.assertEqual(w['research'],1);self.assertEqual(w['reports'],0);self.assertEqual(result['totals']['undated'],1)

    def test_failed_coverage_and_zero_baseline_withhold_growth(self):
        result=aggregate([paper()],self.state(True));self.assertTrue(all(w['change_pct'] is None for w in result['weeks']))
        result=aggregate([paper()],self.state());self.assertIsNone(result['weeks'][-2]['change_pct'])

    def test_crossref_partial_dates_remain_partial(self):
        r=parse_crossref([{'DOI':'10.1234/a','title':['Quantum channels'],'published':{'date-parts':[[2026,9]]}}],NOW)[0]
        self.assertIsNone(r['published_at']);self.assertEqual(r['date_precision'],'month')

    def test_qip_nested_merge_entries_and_author_separator(self):
        body=b'<ol><li>Merge<ol><li><u>Quantum algorithm one:</u> Alice, Bob</li><li><u>Quantum algorithm two</u>: Carol, Dave</li></ol></li><li><u>Quantum algorithm three:</u> Eve</li></ol>'
        source=dict(id='qip',url='https://example.org/qip',venue='QIP',event_start='2026-01-26',event_end='2026-01-30')
        rows=parse_qip(body,source,NOW);self.assertEqual(len(rows),3);self.assertEqual(rows[0]['authors'],['Alice','Bob']);self.assertIsNone(rows[0]['published_at'])

    def test_arxiv_invalid_response_is_not_zero_papers(self):
        with self.assertRaises(ValueError):parse_arxiv(b'<feed/>',NOW)

    def test_osti_filters_product_type_and_retains_calendar_date(self):
        items=[dict(osti_id='1',title='Quantum algorithms',product_type='Technical Report',publication_date='2026-09-01T00:00:00Z'),
               dict(osti_id='2',title='Quantum data',product_type='Dataset')]
        rows=parse_osti(items,NOW);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['published_at'],'2026-09-01')

    def test_required_source_failure_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            a=paper();save_records(directory,[a]);state=Path(directory)/'state.json';state.write_text(json.dumps(dict(last_success=NOW,sources={})))
            before=state.read_bytes()
            with patch('pipeline.collect.ADAPTERS',{'arxiv':lambda *a,**k:(_ for _ in ()).throw(RuntimeError('offline'))}):
                code=collect(Namespace(data_dir=directory,weeks=12,sources='arxiv',as_of=NOW))
            self.assertEqual(code,1);self.assertEqual(state.read_bytes(),before);self.assertEqual(read_records(directory),[a])


if __name__=='__main__':unittest.main()
