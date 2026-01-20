import logging
import threading
from abc import ABC, abstractmethod

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential

from .usage_log import _Timer, log_usage

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)


class BaseEmbeddingModel(ABC):
    @abstractmethod
    def create_embedding(self, text):
        pass


class OpenAIEmbeddingModel(BaseEmbeddingModel):
    def __init__(self, model="text-embedding-ada-002"):
        self.model = model
        # The OpenAI client uses an underlying HTTP client that may not be safe to share
        # across threads. Create one client per thread (important when building embeddings
        # with ThreadPoolExecutor).
        self._tls = threading.local()

    def _client(self) -> OpenAI:
        c = getattr(self._tls, "client", None)
        if c is None:
            c = OpenAI()
            self._tls.client = c
        return c

    # Embeddings can hit rate limits; use more patient exponential backoff.
    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(12))
    def create_embedding(self, text):
        t = _Timer()
        text = (text or "").replace("\n", " ").strip()
        # Avoid invalid empty inputs for embeddings API.
        if not text:
            text = " "
        resp = self._client().embeddings.create(input=[text], model=self.model)
        log_usage(
            kind="embeddings",
            model=self.model,
            usage=getattr(resp, "usage", None),
            duration_s=t.elapsed(),
        )
        return resp.data[0].embedding


class SBertEmbeddingModel(BaseEmbeddingModel):
    def __init__(self, model_name="sentence-transformers/multi-qa-mpnet-base-cos-v1"):
        # Import lazily to avoid hard dependency / version-coupling at module import time.
        # (Some environments will have transformers + huggingface_hub versions that break old sentence-transformers.)
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:  # pragma: no cover
            raise ImportError(
                "SBertEmbeddingModel requires the 'sentence-transformers' package to be installed "
                "and compatible with your 'huggingface_hub' version."
            ) from e

        self.model = SentenceTransformer(model_name)

    def create_embedding(self, text):
        return self.model.encode(text)
