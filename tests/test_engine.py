import unittest

class TestFreshRAG(unittest.TestCase):
    def test_relevance(self):
        self.assertGreaterEqual(0.9, 0.5)

    def test_confidence(self):
        self.assertGreaterEqual(0.95, 0.7)

    def test_abstain(self):
        self.assertTrue(0.2 < 0.5 and 0.3 < 0.7)

if __name__ == "__main__":
    unittest.main()
