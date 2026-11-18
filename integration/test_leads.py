import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from lead_server import LeadService


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = LeadService(self.temp.name + '/test.sqlite', 'example.amocrm.ru', 'test',
                                   1, 'https://example.com', 'https://example.com/', 'v1', 123)
        self.service.deliver = Mock(return_value='crm-receipt')
        self.payload = dict(request_id=str(uuid.uuid4()), name='Тест', company='Тест',
                            email='test@example.com', phone='', trips='', consent=True,
                            consent_version='v1', page='https://example.com/', website='',
                            quiz={}, attribution={})

    def test_repeated_request_does_not_create_twice(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.service.submit, [self.payload, self.payload]))
        self.assertTrue(any(body['status'] == 'created' for _, body in results))
        self.assertEqual(self.service.submit(self.payload)[1]['status'], 'created')
        self.service.deliver.assert_called_once()

    def test_timeout_is_not_retried_blindly(self):
        self.service.deliver.side_effect = TimeoutError()
        self.assertEqual(self.service.submit(self.payload)[1]['status'], 'pending')
        self.assertEqual(self.service.submit(self.payload)[1]['status'], 'pending')
        self.service.deliver.assert_called_once()

    def test_changed_payload_cannot_reuse_key(self):
        self.service.submit(self.payload)
        changed = dict(self.payload, email='other@example.com')
        self.assertEqual(self.service.submit(changed)[0], 409)
        self.service.deliver.assert_called_once()

    def test_invalid_consent_or_email_never_reaches_crm(self):
        self.assertEqual(self.service.submit(dict(self.payload, consent=False))[0], 400)
        self.assertEqual(self.service.submit(dict(self.payload, email='bad'))[0], 400)
        self.service.deliver.assert_not_called()


if __name__ == '__main__':
    unittest.main()
