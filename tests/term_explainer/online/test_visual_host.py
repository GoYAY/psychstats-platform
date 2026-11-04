import json,hashlib
from dataclasses import replace
from .helpers import OnlineCase
from term_explainer.online.config import load_config

class HostTests(OnlineCase):
    def test_only_trusted_complete_build_grants_host(self):
        from term_explainer.online.orchestrator import visual_host_for_config
        config=replace(load_config(self.env),visual_intent_enabled=True);root=config.public_root;root.mkdir()
        self.assertIsNone(visual_host_for_config(config))
        content=b'export const chart=true;';manifest=dict(version=1,entry='entry.mjs',resources=[dict(file='entry.mjs',sha256=hashlib.sha256(content).hexdigest())])
        directory='charts-'+hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:16]
        assets=root/'assets'/directory;assets.mkdir(parents=True);(assets/'manifest.json').write_text(json.dumps(manifest));(assets/'entry.mjs').write_bytes(content)
        report=dict(visualPresentationVersion=1,chartDirectory=directory,chartEntry='entry.mjs');(root/'library-build.json').write_text(json.dumps(report))
        self.assertEqual(visual_host_for_config(config),dict(interactive_chart_types=['bar']))
        for change in [dict(visualPresentationVersion=2),dict(chartDirectory='../private'),dict(chartEntry='../entry.mjs')]:
            (root/'library-build.json').write_text(json.dumps(dict(report,**change)));self.assertIsNone(visual_host_for_config(config))
        (root/'library-build.json').write_text(json.dumps(report));(assets/'entry.mjs').unlink();self.assertIsNone(visual_host_for_config(config))
