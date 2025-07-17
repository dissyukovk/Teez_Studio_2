from django import forms
from .models import STRequest, Product, Order, Invoice

class STRequestForm(forms.ModelForm):
    class Meta:
        model = STRequest
        fields = ['photographer', 'retoucher', 'status', 's_ph_comment', 'sr_comment', 'photos_link']

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['barcode', 'name', 'category', 'in_stock_sum', 'seller', 'move_status', 'retouch_link']

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['date']

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['date', 'creator']
