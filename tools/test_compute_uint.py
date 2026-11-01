"""Real DXC import and isolated-result controls for the explicit uint backend."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from computeformalize import prepare, check, LEGACY
from shader_compute_uint import import_uint_compute, uint_contract
from shader_compute_uint_lean import generate_uint_compute
from shader_ast import ModelError
from shaderformalize import ROOT, validate_dxc, local_environment, workspace_lock
from run_compute_uint_suite import read_run_result


class UintComputeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dxc = validate_dxc()
        cls.source = (ROOT / 'examples/compute-uint/hash.optimized.hlsl').read_text(encoding='utf-8')
        cls.contract = json.loads((ROOT / 'examples/compute-uint/hash.constraints.json').read_text())

    def compile(self, source):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'input.hlsl'; path.write_text(source,encoding='utf-8')
            result = subprocess.run([str(self.dxc),'-T','cs_6_0','-E','main','-HV','2021','-ast-dump',str(path)],env=local_environment(),capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            return import_uint_compute(source,result.stdout)

    def cli(self, container, *extra):
        return subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/computeformalize.py'),'prepare','--model','uint32-buffer','--output',str(container),*extra],cwd=ROOT,env=local_environment(),capture_output=True,text=True,encoding='utf-8',timeout=90)

    def test_timeout_reaps_owned_child_and_keeps_log(self):
        import ctypes
        from shaderformalize import run_tool
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); pidfile=p/'child.pid'; log=p/'timeout.log'
            script="import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);Path(sys.argv[1]).write_text(str(p.pid));print('started',flush=True);time.sleep(60)"
            with self.assertRaisesRegex(ModelError,'process tree'):
                run_tool([sys.executable,'-c',script,str(pidfile)],ROOT,log,timeout=3)
            self.assertIn('started',log.read_text())
            pid=int(pidfile.read_text())
            handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid)
            if handle:
                code=ctypes.c_ulong();ctypes.windll.kernel32.GetExitCodeProcess(handle,ctypes.byref(code))
                ctypes.windll.kernel32.CloseHandle(handle)
                self.assertNotEqual(code.value,259,'Timed-out child still active')

    def test_legacy_direct_prepare_needs_no_model_argument(self):
        import argparse
        with tempfile.TemporaryDirectory() as d:
            args=argparse.Namespace(original=ROOT/'examples/compute/original.hlsl',
                optimized=ROOT/'examples/compute/optimized.hlsl',constraints=ROOT/'examples/compute/constraints.json')
            with workspace_lock():
                report=prepare(args,Path(d))
            self.assertEqual(report['model_schema'],'compute-1')
            text=(Path(d)/'GeneratedModel.lean').read_text(encoding='utf-8')
            self.assertIn('import ShaderFormalize.Compute',text)
            self.assertNotIn('ShaderComputeUint',text)

    def test_actual_hash_and_wrap(self):
        a=self.compile((ROOT/'examples/compute-uint/hash.original.hlsl').read_text())
        b=self.compile(self.source)
        self.assertEqual(a['schema'],'compute-uint-1')
        text=generate_uint_compute(a,b,self.contract)
        for term in ['UInt32','safe threads','finish threads initial','4294967295','ShaderIeee.Model.uintMultiply']:
            self.assertIn(term,text)
        self.assertNotIn('Real',text)

    def test_scope_filter(self):
        for declaration in ['float x=1.0;', 'uint2 v=uint2(1u,2u);', 'uint a[2]={1u,2u};', 'uint3 v=tid;']:
            with self.subTest(declaration=declaration), self.assertRaises(ModelError):
                self.compile(self.source.replace('uint i=tid.x;',declaration+'uint i=tid.x;'))
        with self.assertRaises(ModelError):
            self.compile(self.source.replace('uint i=tid.x;','for(uint k=0u;k<2u;++k){} uint i=tid.x;'))

    def test_pure_helper_resources_rejected_even_uncalled(self):
        with self.assertRaisesRegex(ModelError,'main-only'):
            self.compile(self.source.replace('[numthreads','uint Bad(){return Source[0u];}\n[numthreads'))

    def test_count_helper_and_bool(self):
        self.compile(self.source.replace('[numthreads','bool Test(uint a){return a<Count;}\n[numthreads').replace('i>=Count','!Test(i)'))

    def test_rw_read_and_plain_store_only(self):
        self.compile(self.source.replace('uint h=', 'uint q=Output[i]; uint h='))
        with self.assertRaises(ModelError):
            self.compile(self.source.replace('Output[i]=','Output[i]+='))

    def test_contract_strict_and_dead_capacity(self):
        m=self.compile(self.source)
        for field,value in [('schema',True),('schema',1),('dispatch_groups',True),('dispatch_groups',65536),('count_range',[0,129])]:
            c=copy.deepcopy(self.contract);c[field]=value
            with self.assertRaises(ModelError):uint_contract(c,m,m)
        c=copy.deepcopy(self.contract);c['bindings']['Source']['capacity']=0
        uint_contract(c,m,m) # bounds are a proof obligation, not count<=all capacities
        c['bindings']['Output']['identity']=0
        with self.assertRaises(ModelError):uint_contract(c,m,m)
        c=copy.deepcopy(self.contract);c['extra']=1
        with self.assertRaises(ModelError):uint_contract(c,m,m)

    def test_guards_really_guard_tail_loads(self):
        m=self.compile((ROOT/'examples/compute-uint/guards.hlsl').read_text())
        loads=[e for e in m['events'] if e.get('kind')=='load']
        self.assertEqual(len(loads),3)
        self.assertTrue(all(e['guard']!={'kind':'boolean','width':'bool','value':True} for e in loads))
        self.assertEqual(m['numthreads'],64)

    def test_busy_bad_input_owns_separate_terminal_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);history=p/'result.json';history.write_text('{"status":"PROVED"}')
            with workspace_lock():
                one=self.cli(p,'--constraints',str(p/'missing.json'))
                two=self.cli(p,'--original',str(p/'missing.hlsl'))
            a=read_run_result(one,p);b=read_run_result(two,p)
            self.assertEqual(a['status'],'INCONCLUSIVE');self.assertEqual(b['status'],'INCONCLUSIVE')
            self.assertNotEqual(a['run_id'],b['run_id'])
            self.assertEqual(json.loads(history.read_text())['status'],'PROVED')

    def test_missing_and_bad_json_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            result=read_run_result(self.cli(p,'--constraints',str(p/'missing')),p)
            self.assertEqual(result['status'],'INVALID_INPUT')
            bad=p/'bad.json';bad.write_text('{')
            result=read_run_result(self.cli(p,'--constraints',str(bad)),p)
            self.assertEqual(result['status'],'INVALID_INPUT')

    def test_busy_owner_artifacts_survive_same_and_other_containers(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);container=p/'runs';other=p/'other';ready=p/'ready';release=p/'release'
            script = """import sys,time,argparse
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tools'))
import computeformalize as cf
root=Path(sys.argv[1]);ready=Path(sys.argv[2]);release=Path(sys.argv[3])
def owned(args,out,**kwargs):
    (out/'owner.input.hlsl').write_text('immutable source')
    (out/'owner.log').write_text('running')
    ready.write_text(str(out))
    deadline=time.monotonic()+30
    while not release.exists():
        if time.monotonic()>deadline:raise RuntimeError('fixture release timeout')
        time.sleep(.03)
    (out/'owner.log').write_text('completed')
    return {'status':'PREPARED'}
cf.prepare=owned
sys.exit(cf.uint_main(argparse.Namespace(output=root,command='prepare')))
"""
            owner=subprocess.Popen([sys.executable,'-X','utf8','-c',script,str(container),str(ready),str(release)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
            try:
                deadline=time.monotonic()+15
                while not ready.exists():
                    self.assertIsNone(owner.poll())
                    if time.monotonic()>deadline:self.fail('owner did not acquire workspace')
                    time.sleep(.03)
                owned=Path(ready.read_text());original=(owned/'owner.input.hlsl').read_bytes()
                for target in (container,other):
                    rejected=read_run_result(self.cli(target,'--constraints',str(p/'missing.json')),target)
                    self.assertEqual(rejected['status'],'INCONCLUSIVE')
                    self.assertNotEqual(rejected['run_id'],owned.name)
                    self.assertEqual((owned/'owner.input.hlsl').read_bytes(),original)
                    self.assertEqual((owned/'owner.log').read_text(),'running')
            finally:
                release.write_text('release')
                stdout,stderr=owner.communicate(timeout=30)
            result=read_run_result(subprocess.CompletedProcess([],owner.returncode,stdout,stderr),container)
            self.assertEqual(result['status'],'PREPARED')
            self.assertEqual((owned/'owner.log').read_text(),'completed')

    def test_bad_tool_terminal_and_busy_precedence(self):
        import argparse
        from contextlib import redirect_stdout
        import io
        import computeformalize as cf
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            args=argparse.Namespace(output=p,command='prepare',constraints=ROOT/'examples/compute-uint/hash.constraints.json')
            for busy in (False,True):
                stream=io.StringIO()
                with patch.object(cf,'validate_dxc',side_effect=ModelError('bad pinned tool','ENVIRONMENT_ERROR')) as tool:
                    with redirect_stdout(stream):
                        if busy:
                            with workspace_lock():code=cf.uint_main(args)
                        else:code=cf.uint_main(args)
                    envelope=json.loads(stream.getvalue().strip())
                    report=json.loads(Path(envelope['result_path']).read_text())
                    self.assertEqual(code,1)
                    self.assertEqual(report['status'],'INCONCLUSIVE' if busy else 'ENVIRONMENT_ERROR')
                    self.assertEqual(tool.call_count,0 if busy else 1)

    def test_interrupt_during_initial_report_has_terminal(self):
        import argparse
        from contextlib import redirect_stdout
        import io
        import computeformalize as cf
        with tempfile.TemporaryDirectory() as d:
            args=argparse.Namespace(output=Path(d),command='prepare')
            actual=cf.atomic_result
            calls=[]
            def interrupt_once(path,result):
                calls.append(result['status'])
                if len(calls)==1:raise KeyboardInterrupt()
                actual(path,result)
            stream=io.StringIO()
            with patch.object(cf,'atomic_result',side_effect=interrupt_once), redirect_stdout(stream):
                code=cf.uint_main(args)
            envelope=json.loads(stream.getvalue())
            report=json.loads(Path(envelope['result_path']).read_text())
            self.assertEqual(code,1)
            self.assertEqual(calls,['IN_PROGRESS','INCONCLUSIVE'])
            self.assertEqual(report['status'],'INCONCLUSIVE')

    def test_exclusive_run_collision_cannot_take_owner(self):
        import argparse
        from contextlib import redirect_stdout,redirect_stderr
        import io
        import uuid
        import computeformalize as cf
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);key='f'*32;owned=root/key;owned.mkdir()
            report=owned/'result.json';original=b'{"status":"PROVED","owner":"existing"}'
            report.write_bytes(original)
            stdout,stderr=io.StringIO(),io.StringIO()
            with patch.object(cf.uuid,'uuid4',return_value=uuid.UUID(hex=key)),redirect_stdout(stdout),redirect_stderr(stderr):
                code=cf.uint_main(argparse.Namespace(output=root,command='prepare'))
            self.assertEqual(code,1)
            self.assertEqual(stdout.getvalue(),'')
            self.assertIn('Cannot save',stderr.getvalue())
            self.assertEqual(report.read_bytes(),original)

    def test_runner_rejects_old_success(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'result.json').write_text('{"status":"PROVED"}')
            fake=subprocess.CompletedProcess([],0,'{"status":"PROVED","run_id":"ffffffffffffffffffffffffffffffff","result_path":"'+str(p/'result.json').replace('\\','\\\\')+'"}','')
            with self.assertRaises(ValueError):read_run_result(fake,p)


if __name__=='__main__':unittest.main()
