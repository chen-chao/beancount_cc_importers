import os
import tempfile
import hashlib
import json
from typing import Optional, Union

from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient


class JsonAccessor:
    def __init__(self, properties: Union[dict, list]):
        self.properties = properties

    def __getattr__(self, name):
        name = self._getCamelCase(name)

        if isinstance(self.properties, dict):
            prop = self.properties.get(name)
            return JsonAccessor.wrap(prop)

        raise AttributeError(name)

    def __getitem__(self, key):
        if isinstance(self.properties, list):
            return JsonAccessor.wrap(self.properties[key])

        raise AttributeError(key)

    def __len__(self):
        return len(self.properties)

    def __iter__(self):
        for prop in self.properties:
            yield JsonAccessor.wrap(prop)

    @staticmethod
    def wrap(prop):
        if isinstance(prop, dict) or isinstance(prop, list):
            return JsonAccessor(prop)

        return prop

    def _getCamelCase(self, name: str):
        # transform snake_case to camelCase
        camel_case = []
        for i in range(len(name)):
            if name[i] == "_":
                continue
            if i > 0 and name[i - 1] == "_":
                camel_case.append(name[i].upper())
            else:
                camel_case.append(name[i].lower())

        name = "".join(camel_case)
        return name

# https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/choose-model-feature?view=doc-intel-4.0.0
# models:
# - prebuilt-layout, to extract structural information like tables, paragraphs, titles, headings.
# - prebuilt-read, for OCR.
# - prebuilt-receipt, for receipts.
# - prebuilt-invoice, for invoices.
class AzureDocumentRecognizer:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        model: str = "prebuilt-layout",
        cache_dir: Optional[str] = None,
    ):
        endpoint = endpoint or os.environ.get("AZURE_FORM_RECOGNIZER_ENDPOINT")
        if endpoint is None:
            raise ValueError(
                "Please provide your endpoint in the environment variable AZURE_FORM_RECOGNIZER_ENDPOINT"
            )

        key = key or os.environ.get("AZURE_FORM_RECOGNIZER_KEY")
        if key is None:
            raise ValueError(
                "Please provide your API key in the environment variable AZURE_FORM_RECOGNIZER_KEY"
            )

        self.client = DocumentAnalysisClient(
            endpoint=endpoint, credential=AzureKeyCredential(key)
        )

        self.model = model

        if cache_dir is None:
            # create a temporary directory with prefix 'azure_form_recognizer'
            cache_dir = tempfile.TemporaryDirectory(
                prefix="azure_form_recognizer"
            )

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        self.cache_dir = cache_dir

    def analyze(self, file_name: str):
        file_hash = self._hash_file(file_name)
        basename, ext = os.path.splitext(file_name)
        cache_file = os.path.join(self.cache_dir, f"{basename}{file_hash}{ext}")

        if os.path.exists(cache_file):
            result = json.load(open(cache_file, "r"))
            return JsonAccessor.wrap(result)

        # analyze the document and save the result to the cache file
        with open(file_name, "rb") as f:
            poller = self.client.begin_analyze_document(self.model, document=f)

        result = poller.result()
        with open(cache_file, "w") as f:
            json.dump(result, f)

        return result

    def _hash_file(self, file_name: str, prefix: int = 8):
        with open(file_name, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:prefix]
