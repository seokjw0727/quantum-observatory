"""Small synthetic snapshot strictly for CI build validation, never for publishing."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.model import make_record,atomic_json
from pipeline.collect import save_records

path=Path('.cache/ci-data')
now='2026-09-07T00:17:00Z'
record=make_record('arxiv','test-fixture','TEST FIXTURE: quantum error correction','preprint','https://example.org/test',now,published_at='2026-09-01')
save_records(path,[record])
atomic_json(path/'state.json',dict(run_id='ci-fixture',last_success=now,sources={},content_hash='fixture',code_sha='fixture',status='partial',snapshot_type='fixture'))
