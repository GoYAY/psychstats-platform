from dataclasses import asdict
from term_explainer.online.config import load_config,OnlineError
from .helpers import OnlineCase

class ConfigTests(OnlineCase):
    def test_visual_policy_is_server_only_default_off(self):
        self.assertFalse(load_config(self.env).visual_intent_enabled)
        self.assertTrue(load_config(dict(self.env,TERM_VISUAL_INTENT_ENABLED='true')).visual_intent_enabled)
        with self.assertRaises(OnlineError):load_config(dict(self.env,TERM_VISUAL_INTENT_ENABLED='yes'))
    def test_generation_kill_switch_defaults_off_and_requires_boolean_text(self):
        self.assertFalse(load_config(self.env).generation_enabled)
        self.assertTrue(load_config({**self.env,'TERM_GENERATION_ENABLED':'true'}).generation_enabled)
        with self.assertRaises(OnlineError):load_config({**self.env,'TERM_GENERATION_ENABLED':'yes'})

    def test_https_loopback_preview_can_use_explicit_nonstandard_port(self):
        config=load_config({**self.env,'TERM_ORIGIN':'https://127.0.0.1:8874'})
        self.assertEqual(config.origin,'https://127.0.0.1:8874')

    def test_config_requires_explicit_limits_and_does_not_include_credentials(self):
        env={**self.env,'DEEPSEEK_API_KEY':'never-serialize-this'}
        config=load_config(env)
        self.assertEqual(config.limits.max_job_calls,80)
        self.assertEqual(config.api_prefix,'/psy-stats-test/api/term-explainer/')
        self.assertNotIn('never-serialize-this',str(asdict(config)))
        for key in [k for k in env if k.startswith('TERM_MAX_')]+['TERM_REQUEST_TIMEOUT']:
            missing=dict(env);missing.pop(key)
            with self.subTest(key=key),self.assertRaises(OnlineError):load_config(missing)

    def test_private_and_public_paths_cannot_overlap_or_follow_symlinks(self):
        for private in [str(self.root),str(self.root/'public'),str(self.root/'public'/'secret')]:
            with self.subTest(private=private),self.assertRaises(OnlineError):
                load_config({**self.env,'TERM_PRIVATE_ROOT':private})
        self.assertFalse((self.root/'private').exists(),'Validation must not create directories')

    def test_negative_boolean_noninteger_and_untrusted_origins_rejected(self):
        for value in ['0','-1','True','1.5','1000000000000000000']:
            with self.subTest(value=value),self.assertRaises(OnlineError):
                load_config({**self.env,'TERM_MAX_FILES':value})
        for origin in ['http://cdst.site','https://u:p@cdst.site','https://cdst.site/path','https://cdst.site?x=1']:
            with self.subTest(origin=origin),self.assertRaises(OnlineError):load_config({**self.env,'TERM_ORIGIN':origin})
        for prefix in ['/','/../api/','/api?x/','api/']:
            with self.subTest(prefix=prefix),self.assertRaises(OnlineError):load_config({**self.env,'TERM_API_PREFIX':prefix})
