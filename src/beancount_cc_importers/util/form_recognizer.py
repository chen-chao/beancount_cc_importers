import os

from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient


class AzureFormRecognizer:
    def __init__(self, endpoint=None, key=None):
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
        self.model = "prebuilt-layout"

    def analyze(self, file_name: str):
        with open(file_name, "rb") as f:
            poller = self.client.begin_analyze_document(self.model, document=f)

        return poller.result().tables
