import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'job-worker'))
from application_answers import answer_for, required_unknown


class ApplicationAnswerTests(unittest.TestCase):
    def setUp(self):
        self.config = {'personals': {'first_name': 'Test', 'last_name': 'Owner', 'phone_number': '+971 50 000 0000', 'current_city': 'Dubai'},
                       'questions': {'years_of_experience': '20', 'require_visa': 'No', 'legally_authorized': '', 'notice_period': 0, 'desired_salary': 0}}

    def test_known_contact_and_immediate_notice_can_be_used(self):
        self.assertEqual(answer_for('First name *', self.config), 'Test')
        self.assertEqual(answer_for('Country calling code', self.config), '+971')
        self.assertEqual(answer_for('Notice period in days', self.config), '0')

    def test_career_years_do_not_answer_skill_tenure(self):
        self.assertEqual(answer_for('Total years of experience', self.config), '20')
        self.assertIsNone(answer_for('How many years of Linux experience do you have?', self.config))
        self.assertIsNone(answer_for('Years of production AWS experience', self.config))

    def test_residency_never_creates_a_work_permit_answer(self):
        self.config['questions']['residency'] = 'UAE investor residency'
        self.assertIsNone(answer_for('Are you legally authorized to work?', self.config))
        self.assertEqual(answer_for('Do you require visa sponsorship?', self.config), 'No')
        self.assertIsNone(answer_for('Do you require sponsorship in the United States?', self.config))

    def test_unset_or_unqualified_salary_is_not_entered(self):
        self.assertIsNone(answer_for('Expected salary', self.config))
        self.config['questions']['desired_salary'] = 10000
        self.assertIsNone(answer_for('Expected annual salary', self.config))

    def test_unfamiliar_prefilled_answer_and_new_legal_terms_still_need_review(self):
        fields = [{'label': 'Production Azure years', 'required': True, 'value': '10'},
                  {'label': 'I agree to binding arbitration', 'required': True, 'value': True},
                  {'label': 'First name', 'required': True, 'value': 'Test'}]
        self.assertEqual(required_unknown(fields, self.config), ['Production Azure years', 'I agree to binding arbitration'])
