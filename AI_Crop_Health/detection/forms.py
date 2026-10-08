from django import forms

class PlantDiseaseUploadForm(forms.Form):
    image = forms.ImageField(
        label='Plant Image',
        help_text='Upload JPG, JPEG, or PNG image',
        widget=forms.FileInput(attrs={
            'accept': 'image/jpeg,image/jpg,image/png',
            'class': 'form-control'
        })
    )

class InsectUploadForm(forms.Form):
    image = forms.ImageField(
        label='Insect Photo',
        help_text='Close-up of a single insect. JPG, JPEG or PNG.',
        widget=forms.FileInput(attrs={
            'accept': 'image/jpeg,image/jpg,image/png',
            'class': 'form-control'
        })
    )
