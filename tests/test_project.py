"""Offline tests: schema adapters, safe local serving, reproducible native archives.
These do not emulate KWGT's formula engine or Android background execution.
"""
from __future__ import annotations
import copy
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

connector, build, serve = load('connector'), load('build'), load('serve')

class AdapterTests(unittest.TestCase):
    def result(self, value, mode='remaining', **extra):
        document = {'value': value, **extra}
        mapping = {'value': 'value', 'mode': mode}
        if 'total' in extra: mapping['total'] = 'total'
        return connector.normalize(document, mapping)

    def test_remaining(self):
        self.assertEqual(self.result(64)['weekly']['remaining'], 64)

    def test_used(self):
        self.assertEqual(self.result(36, 'used')['weekly']['remaining'], 64)

    def test_fraction(self):
        self.assertAlmostEqual(self.result(.64, 'fraction')['weekly']['remaining'], 64)

    def test_ratio(self):
        self.assertEqual(self.result(640, 'ratio', total=1000)['weekly']['remaining'], 64)

    def test_unknown_age_is_not_fabricated(self):
        self.assertIsNone(self.result(64)['refreshedAt'])
        self.assertIsNone(self.result(64)['weekly']['resetsAt'])

    def test_timestamp_timezone_and_precision(self):
        self.assertEqual(connector.timestamp('2026-01-01T12:00:00.1234567-04:00'),
                         '2026-01-01T12:00:00-04:00')
        self.assertEqual(connector.timestamp('2026-01-01T12:00:00Z'),
                         '2026-01-01T12:00:00+00:00')

    def test_invalid_timestamps_rejected(self):
        for invalid in ('2026-01-01', 'now', '2026-01-01T12:00:00', 123):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                connector.timestamp(invalid)

    def test_non_numeric_and_non_finite_rejected(self):
        for invalid in (True, False, '64', None, float('nan'), float('inf')):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                self.result(invalid)

    def test_out_of_range_rejected_not_clamped(self):
        for invalid in (-1, 101):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                self.result(invalid)
        with self.assertRaises(ValueError): self.result(1, 'ratio', total=0)

    def test_unavailable_without_number(self):
        out = connector.normalize({'ok': False}, {'available': 'ok'})
        self.assertEqual(out['weekly'], {'available': False, 'remaining': None, 'resetsAt': None})

    def test_availability_is_boolean(self):
        with self.assertRaises(ValueError):
            connector.normalize({'ok': 'true', 'value': 64}, {'value': 'value', 'available': 'ok'})

    def test_list_and_nested_paths(self):
        self.assertEqual(connector.field({'a': [{'b': 64}]}, 'a.0.b'), 64)

    def test_private_fields_are_not_copied(self):
        result = self.result(64, token='private-test-token', accountId='private-test-account')
        rendered = json.dumps(result)
        self.assertNotIn('private-test', rendered)
        self.assertEqual(set(result), {'weekly', 'refreshedAt'})

    def test_unknown_mapping_or_mode_rejected(self):
        with self.assertRaises(ValueError):
            connector.normalize({}, {'unexpected': 'key'})
        with self.assertRaises(ValueError): self.result(64, 'unknown')

    def test_examples(self):
        for name in ('api', 'storage'):
            with self.subTest(name=name):
                payload = json.loads((ROOT/'examples'/f'{name}-response.json').read_text())
                mapping = json.loads((ROOT/'examples'/f'{name}-mapping.json').read_text())
                self.assertEqual(connector.normalize(payload, mapping)['weekly']['remaining'], 64)

    def test_atomic_write_preserves_old_on_serialization_failure(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)/'usage.json'
            connector.atomic_write(target, self.result(64))
            old = target.read_bytes()
            with self.assertRaises(ValueError): connector.atomic_write(target, {'value': float('nan')})
            self.assertEqual(target.read_bytes(), old)
            self.assertEqual([p.name for p in Path(td).iterdir()], ['usage.json'])

    def test_failed_cli_preserves_old_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder/'input.json').write_text('{"value": 123}')
            (folder/'mapping.json').write_text('{"value": "value"}')
            (folder/'usage.json').write_text('{"old": true}')
            args = [sys.executable, str(ROOT/'tools/connector.py'), '--input', str(folder/'input.json'),
                    '--mapping', str(folder/'mapping.json'), '--output', str(folder/'usage.json')]
            result = subprocess.run(args, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((folder/'usage.json').read_text(), '{"old": true}')

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.file = Path(self.temp.name)/'usage.json'
        self.file.write_text('{"weekly":{"available":true,"remaining":64}}')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), serve.make_handler(self.file))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(3)
        self.temp.cleanup()

    def test_get_and_cache_busting_query(self):
        with urlopen(self.url+'/usage.json?kwgt=123&tap=456', timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response)['weekly']['remaining'], 64)
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')

    def test_no_directory_listing_or_arbitrary_files(self):
        for path in ('/', '/auth.json', '/../usage.json'):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                urlopen(self.url+path, timeout=3)
            self.assertEqual(error.exception.code, 404)

    def test_invalid_and_missing_payload_not_served(self):
        self.file.write_text('not json')
        with self.assertRaises(HTTPError) as error: urlopen(self.url+'/usage.json', timeout=3)
        self.assertEqual(error.exception.code, 503)
        self.file.unlink()
        with self.assertRaises(HTTPError) as error: urlopen(self.url+'/usage.json', timeout=3)
        self.assertEqual(error.exception.code, 503)

    def test_oversized_payload_rejected(self):
        self.file.write_bytes(b' '*1_048_577)
        with self.assertRaises(HTTPError) as error: urlopen(self.url+'/usage.json', timeout=3)
        self.assertEqual(error.exception.code, 503)

class PresetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = [(p, json.loads(p.read_text())) for p in sorted((ROOT/'src').glob('*/preset.json'))]

    def test_exactly_six_native_sources(self):
        self.assertEqual(len(self.sources), 6)
        for path, data in self.sources:
            with self.subTest(theme=path.parent.name):
                root = data['preset_root']
                self.assertTrue(root['viewgroup_items'])
                self.assertTrue(all(x['internal_type']=='ShapeModule' for x in root['viewgroup_items']))
                self.assertNotIn('BitmapModule', json.dumps(data))
                self.assertNotIn('br(tasker', json.dumps(data).lower())
                self.assertNotIn('kfile://', json.dumps(data))

    def test_public_defaults_and_no_private_hostnames(self):
        for path, data in self.sources:
            with self.subTest(theme=path.parent.name):
                globals_ = data['preset_root']['globals_list']
                self.assertEqual(globals_['source']['value'], build.PLACEHOLDER)
                self.assertEqual(globals_['latch']['value'], '0~~~~')
                text = json.dumps(data)
                self.assertNotRegex(text, r'[\w.-]+\.ts\.net')
                self.assertNotRegex(text, r'100\.\d+\.\d+\.\d+')
                self.assertNotIn('desktop-', text)

    def test_default_customization_is_identity(self):
        for _, data in self.sources:
            self.assertEqual(data, build.customize(data))

    def test_pack_is_reproducible_and_embeds_only_json_and_thumbnails(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            first = build.build(folder/'one')
            second = build.build(folder/'two')
            self.assertEqual(len(first), 6)
            for one, two in zip(first, second):
                self.assertEqual(one.read_bytes(), two.read_bytes())
                with zipfile.ZipFile(one) as archive:
                    self.assertEqual(set(archive.namelist()), {'preset.json', 'preset_thumb_landscape.jpg',
                                                              'preset_thumb_portrait.jpg'})
                    self.assertIsNone(archive.testzip())
                    data = json.loads(archive.read('preset.json'))
                    self.assertEqual(data['preset_root']['globals_list']['source']['value'], build.PLACEHOLDER)

    def test_header_rebuild_preserves_data_logic(self):
        for path, data in self.sources:
            with self.subTest(theme=path.parent.name):
                custom = build.customize(data, label='API RESERVE', source_label='SOURCE')
                self.assertEqual(data['preset_root']['internal_events'],
                                 custom['preset_root']['internal_events'])
                headers = [i for i in custom['preset_root']['viewgroup_items']
                           if i.get('internal_title', '').startswith('HEADER /')]
                self.assertTrue(headers)
                self.assertTrue(all('M0 0' in i['shape_path'] for i in headers))
                self.assertNotIn('PC DATA', json.dumps(custom))
                self.assertEqual(len(data['preset_root']['viewgroup_items']),
                                 len(custom['preset_root']['viewgroup_items']))

    def test_unsupported_header_and_source_labels_fail(self):
        data = self.sources[0][1]
        for label in ('x'*21, '中文'):
            with self.subTest(label=label), self.assertRaises(ValueError):
                build.customize(data, label=label)
        with self.assertRaises(ValueError): build.customize(data, source_label='too long label')

    def test_all_used_pixel_globals_resolve(self):
        for path, data in self.sources:
            with self.subTest(theme=path.parent.name):
                keys = data['preset_root']['globals_list']
                for variable in re.findall(r'gv\((p\d+)\)', json.dumps(data)):
                    self.assertIn(variable, keys)

if __name__ == '__main__':
    unittest.main()
