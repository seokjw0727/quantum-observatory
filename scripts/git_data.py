"""Restore/persist only the generated data branch, without switching the source checkout."""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def git(*args,cwd=None,capture=True,check=True):
    return subprocess.run(['git',*args],cwd=cwd,check=check,stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def exists_remote():
    result=git('ls-remote','--exit-code','--heads','origin','data',check=False)
    if result.returncode==2:return False
    if result.returncode:raise RuntimeError('Cannot inspect the remote data branch; refusing to assume it is empty')
    return True


def restore(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if not exists_remote():
        print('No data branch yet; the first collection will backfill.');return
    git('fetch','origin','data','--depth=1')
    paths=git('ls-tree','-r','--name-only','FETCH_HEAD').stdout.decode().splitlines()
    for value in paths:
        path=Path(value)
        if path.is_absolute() or '..' in path.parts:raise ValueError('Invalid remote data path')
        if not (value in {'state.json','last-attempt.json'} or value.startswith(('records/','runs/'))):continue
        dest=directory/path;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(git('show',f'FETCH_HEAD:{value}').stdout)
    print('Restored data at '+git('rev-parse','FETCH_HEAD').stdout.decode().strip())


def persist(directory):
    directory=Path(directory).resolve()
    state=json.loads((directory/'state.json').read_text())
    remote=exists_remote()
    if remote:git('fetch','origin','data','--depth=1')
    with tempfile.TemporaryDirectory(prefix='quantum-data-') as parent:
        worktree=Path(parent)/'checkout'
        git('worktree','add','--detach',str(worktree),'FETCH_HEAD' if remote else 'HEAD')
        try:
            if not remote:
                git('checkout','--orphan','data-initial',cwd=worktree)
                git('rm','-rf','.',cwd=worktree)
            for name in ['records','runs']:
                dest=worktree/name
                if dest.exists():shutil.rmtree(dest)
                if (directory/name).exists():shutil.copytree(directory/name,dest)
            for name in ['state.json','last-attempt.json']:
                if (directory/name).exists():shutil.copyfile(directory/name,worktree/name)
            git('config','user.name','github-actions[bot]',cwd=worktree)
            git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com',cwd=worktree)
            git('add','-A',cwd=worktree)
            if git('diff','--cached','--quiet',cwd=worktree,check=False).returncode:
                git('commit','-m','data: '+state['run_id'],cwd=worktree)
                # No force push: a concurrent or unexpected remote update fails safely.
                git('push','origin','HEAD:refs/heads/data',cwd=worktree)
            print('Saved data commit '+git('rev-parse','HEAD',cwd=worktree).stdout.decode().strip())
        finally:git('worktree','remove','--force',str(worktree))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['restore','persist']);p.add_argument('--directory',default='data');a=p.parse_args()
    (restore if a.action=='restore' else persist)(a.directory)
