import unittest
from jobs_v2.tailoring import Evidence, tailor

class TailoringTests(unittest.TestCase):
    def setUp(self):
        self.evidence = [
            Evidence("Linux", "Production L3 incident response"),
            Evidence("Kubernetes", "Built kubeadm cluster", "personal_project"),
            Evidence("Azure", "Completed foundational labs", "foundational"),
        ]
        self.contact = {"name": "Test Candidate", "email": "test@example.com"}

    def test_reorders_to_match_role_without_new_claims(self):
        result = tailor("Kubernetes and Linux operations", self.evidence,
                        "Senior Linux infrastructure engineer.", "Example Ltd",
                        "Infrastructure Engineer", self.contact)
        self.assertEqual(result["matched_skills"], ["Linux", "Kubernetes"])
        self.assertIn("Personal project", result["resume_text"])
        self.assertIn("foundational", result["resume_text"].lower())
        self.assertTrue(result["requires_review"])
        self.assertFalse(result["submitted"])

    def test_no_invented_python(self):
        result = tailor("Python required", self.evidence, "Linux engineer.",
                        "Example", "Python Developer", self.contact)
        self.assertEqual(result["matched_skills"], [])
        self.assertNotIn("Python:", result["resume_text"])

    def test_empty_description_rejected(self):
        with self.assertRaises(ValueError):
            tailor("", self.evidence, "Linux engineer.", "Example", "Engineer", self.contact)

if __name__ == "__main__":
    unittest.main()
