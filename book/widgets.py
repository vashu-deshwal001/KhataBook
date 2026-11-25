from django.forms import ClearableFileInput


class ReceiptUpload(ClearableFileInput):
    template_name = 'book/widgets/receipt_upload.html'

    def __init__(self, attrs=None):
        super().__init__({'accept': '.pdf,.jpg,.jpeg,.png,.webp', **(attrs or {})})
