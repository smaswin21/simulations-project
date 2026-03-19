import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import agent_flow.embedding as embedding


class FakeFastEmbedModel:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def embed(self, texts):
        for text in texts:
            yield np.asarray([len(text), 1.0, 2.0], dtype=np.float32)


class FastEmbedSmokeTests(unittest.TestCase):
    def tearDown(self):
        embedding._embed_model = None
        embedding._model_available = None

    def test_get_embed_model_and_embed_text(self):
        fake_module = SimpleNamespace(TextEmbedding=FakeFastEmbedModel)
        with patch.dict("sys.modules", {"fastembed": fake_module}):
            model = embedding.get_embed_model()
            vector = embedding.embed_text("commons fairness")

        self.assertIsNotNone(model)
        self.assertEqual(model.model_name, embedding.EMBEDDING_MODEL)
        self.assertIsInstance(vector, np.ndarray)
        self.assertGreater(vector.size, 0)


if __name__ == "__main__":
    unittest.main()
