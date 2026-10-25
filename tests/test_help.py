import os, re, unittest
from tests import helpers as h

c = h.client
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class HelpGuide(unittest.TestCase):
    def setUp(self): h.reset()

    def test_the_guide_is_served_and_is_the_file_in_the_program_folder(self):
        r = c.get("/api/help"); self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["markdown"], open(os.path.join(ROOT, "HELP.md"), encoding="utf-8").read())

    def test_it_covers_install_configuration_and_the_extras(self):
        md = c.get("/api/help").json()["markdown"]; heads = [l[3:] for l in md.splitlines() if l.startswith("## ")]
        for want in ("Install", "First run", "Choosing the model", "Voice", "Open it from your phone", "Updating", "Troubleshooting"):
            self.assertTrue(any(want in x for x in heads), want)

    def test_every_script_it_tells_you_to_run_exists(self):
        md = c.get("/api/help").json()["markdown"]
        for script in set(re.findall(r"scripts/([a-z_]+\.sh)", md)): self.assertTrue(os.path.exists(os.path.join(ROOT, "scripts", script)), script)
        for path in ("tts/setup.sh", "stt/setup.sh", "bin/start_smartward.sh", "requirements.txt"): self.assertTrue(os.path.exists(os.path.join(ROOT, path)), path)
        self.assertIn("tailscale serve --bg 127.0.0.1:8000", md)

    def test_what_it_says_about_settings_names_things_that_exist(self):
        md = c.get("/api/help").json()["markdown"]
        ui = "".join(open(os.path.join(ROOT, "frontend/src/views", f), encoding="utf-8").read() for f in ("Settings.tsx", "RemoteSettings.tsx", "VoiceSettings.tsx", "Today.tsx"))
        for label in ("Test the model", "OpenRouter free models", "Remote access (phone)", "App lock", "Backup & restore", "Brief me", "Allow my phone to connect", "Keep this laptop awake", "Usage & budget"):
            self.assertIn(label, ui, label)
        for section in ("Model", "Voice", "GitHub", "Export", "Desktop"): self.assertIn(f"Settings → {section}", md)

    def test_a_signed_in_phone_can_read_it_and_a_stranger_cannot(self):
        from tests.test_remote import VIA, turn_on, sign_in
        VIA.pop("Cookie", None); turn_on()
        self.assertEqual(c.get("/api/help", headers=VIA).status_code, 401)
        sign_in(); self.assertEqual(c.get("/api/help", headers=VIA).status_code, 200)    # a phone may read it: its allow-list has to include it


if __name__ == "__main__":
    unittest.main()
