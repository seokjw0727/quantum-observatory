import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/git_data.py'


class DurableDataBranch(unittest.TestCase):
    def test_roundtrip_preserves_main_and_updates_data_without_force_push(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);remote=root/'remote.git';repo=root/'repo'
            def git(*args,cwd=None):
                return subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True).stdout.decode().strip()
            git('init','--bare',str(remote));git('init','-b','main',str(repo))
            git('config','user.name','Test',cwd=repo);git('config','user.email','test@example.invalid',cwd=repo)
            (repo/'source.txt').write_text('source code stays here')
            git('add','source.txt',cwd=repo);git('commit','-m','initial',cwd=repo)
            git('remote','add','origin',str(remote),cwd=repo);git('push','origin','main',cwd=repo)
            head=git('rev-parse','HEAD',cwd=repo)
            payload=repo/'payload';(payload/'records').mkdir(parents=True)
            (payload/'records/arxiv.jsonl').write_text('{"id":"a"}\n')
            (payload/'state.json').write_text(json.dumps({'run_id':'run-one'}))
            subprocess.run([sys.executable,str(SCRIPT),'persist','--directory',str(payload)],cwd=repo,check=True,capture_output=True)
            self.assertEqual(git('rev-parse','HEAD',cwd=repo),head)
            self.assertEqual((repo/'source.txt').read_text(),'source code stays here')
            first=git('ls-remote','origin','refs/heads/data',cwd=repo).split()[0]
            (payload/'state.json').write_text(json.dumps({'run_id':'run-two'}))
            subprocess.run([sys.executable,str(SCRIPT),'persist','--directory',str(payload)],cwd=repo,check=True,capture_output=True)
            second=git('ls-remote','origin','refs/heads/data',cwd=repo).split()[0]
            self.assertNotEqual(first,second)
            restored=repo/'restored'
            subprocess.run([sys.executable,str(SCRIPT),'restore','--directory',str(restored)],cwd=repo,check=True,capture_output=True)
            self.assertEqual(json.loads((restored/'state.json').read_text())['run_id'],'run-two')
            self.assertTrue((restored/'records/arxiv.jsonl').exists())
            self.assertFalse((restored/'source.txt').exists())


if __name__=='__main__':unittest.main()
