import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from lead_server import LeadService, normalize_email, normalize_phone


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = LeadService(self.temp.name + '/test.sqlite', 'example.amocrm.ru', 'test',
                                   1, 'https://example.com', 'https://example.com/', 'v1', 123)
        self.service.deliver = Mock(return_value='crm-receipt')
        self.payload = dict(request_id=str(uuid.uuid4()), name='Тест', company='Тест',
                            email='test@example.com', phone='+74950000000', trips='', consent=True,
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

    def test_quiz_accepts_contacts_without_name_or_company(self):
        quiz = {'1': '2', '2': 'ru', '3': 'short', '4': 'self', '5': 'manual', '6': 'none'}
        payload = dict(self.payload, form_type='quiz', name='', company='', quiz=quiz)
        self.assertEqual(self.service.submit(payload)[1]['status'], 'created')
        self.service.deliver.assert_called_once()

    def test_phone_required_for_both_forms(self):
        self.assertEqual(self.service.submit(dict(self.payload, phone=''))[0], 400)
        self.assertEqual(self.service.submit(dict(self.payload, phone='-------'))[0], 400)
        self.service.deliver.assert_not_called()

    def test_main_still_requires_company(self):
        self.assertEqual(self.service.submit(dict(self.payload, company=''))[0], 400)
        self.service.deliver.assert_not_called()

    def test_quiz_requires_complete_answers(self):
        self.assertEqual(self.service.submit(dict(self.payload, form_type='quiz'))[0], 400)
        self.service.deliver.assert_not_called()

    def test_quiz_crm_payload_has_no_invented_company(self):
        import io
        import json
        from contextlib import nullcontext
        from unittest.mock import patch
        payload = dict(self.payload, form_type='quiz', name='', company='')
        response = {'_embedded': {'unsorted': [{'uid': 'receipt', 'request_id': payload['request_id']}]}}
        with patch('lead_server.urlopen', return_value=nullcontext(io.StringIO(json.dumps(response)))) as request:
            self.assertEqual(LeadService.deliver(self.service, payload), 'receipt')
        sent = json.loads(request.call_args[0][0].data)[0]['_embedded']
        self.assertEqual(sent['companies'], [])
        self.assertEqual(sent['contacts'][0]['custom_fields_values'][1]['field_code'], 'PHONE')


class ContactValidationTests(unittest.TestCase):
    def test_invalid_addresses_are_rejected(self):
        for value in ['', 'name', 'name@company', 'name@company.c', '.name@company.ru',
                      'name..surname@company.ru', 'name@-company.ru', 'name@company..ru',
                      'name@company.123', 'name@company.invalid', 'name@company.test']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_email(value)

    def test_work_addresses_remain_valid(self):
        for value in ['name+travel@company.ru', 'name.surname@sub.company.com', 'a@xn--e1afmkfd.xn--p1ai']:
            self.assertEqual(normalize_email(value), value)

    def test_phone_normalization(self):
        for value, expected in [('8 (495) 123-45-67', '+74951234567'),
                                ('916 123-45-67', '+79161234567'),
                                ('+44 20 7946 0958', '+442079460958'),
                                ('+81 90 1234 567', '+81901234567')]:
            with self.subTest(value=value):
                self.assertEqual(normalize_phone(value), expected)

    def test_obvious_invalid_numbers_are_rejected(self):
        for value in ['', '123', '+7', '4951234567', '+00000000000', '+79999999999',
                      '8 999 123', '++74951234567', '+7abc4951234567', '+12345678901']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_phone(value)


if __name__ == '__main__':
    unittest.main()
