import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from configure_telegram import owner_from_update


class OwnerOnboardingTests(unittest.TestCase):
    def fixture(self):
        return {'message': {'from': {'id': 12345, 'is_bot': False},
                            'chat': {'id': 12345, 'type': 'private'},
                            'text': '/start unique-owner-proof'}}

    def test_private_matching_challenge_identifies_owner(self):
        self.assertEqual(owner_from_update(self.fixture(), 'unique-owner-proof'), 12345)

    def test_unrelated_group_forwarded_and_bot_updates_cannot_enroll(self):
        invalid = []
        for field, value in [('text', '/start wrong'), ('forward_origin', {'type': 'user'}),
                             ('via_bot', {'id': 987})]:
            update = self.fixture()
            update['message'][field] = value
            invalid.append(update)
        for parent, field, value in [('chat', 'type', 'group'), ('chat', 'id', -12345),
                                     ('from', 'is_bot', True), ('from', 'id', 67890)]:
            update = self.fixture()
            update['message'][parent][field] = value
            invalid.append(update)
        invalid.extend([{}, {'message': None}, {'callback_query': self.fixture()['message']}])
        for update in invalid:
            with self.subTest(update=update):
                self.assertIsNone(owner_from_update(update, 'unique-owner-proof'))


if __name__ == '__main__':
    unittest.main()
