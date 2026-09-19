# features/management/commands/load_sample_schemes.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from features.models import SchemeCategory, GovernmentScheme  # Updated import
from decimal import Decimal

class Command(BaseCommand):
    help = 'Load sample government schemes data'

    def handle(self, *args, **kwargs):
        # Create categories
        categories = [
            {'name': 'Agricultural Schemes', 'slug': 'agricultural-schemes'},
            {'name': 'Financial Assistance', 'slug': 'financial-assistance'},
            {'name': 'Insurance Schemes', 'slug': 'insurance-schemes'},
            {'name': 'Other Schemes', 'slug': 'other-schemes'},
        ]
        
        for i, cat_data in enumerate(categories):
            category, created = SchemeCategory.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'display_order': i + 1,
                    'description': f'Government schemes for {cat_data["name"].lower()}'
                }
            )
            if created:
                self.stdout.write(f'Created category: {category.name}')

        # Create sample schemes
        schemes_data = [
            {
                'name': 'National Food Security Mission (NFSM)',
                'ministry': 'Agriculture & Farmers Welfare',
                'budget': Decimal('12500.00'),
                'category_slug': 'agricultural-schemes',
                'description': 'The National Food Security Mission (NFSM) aims to increase production of rice, wheat, pulses, and coarse cereals through area expansion and productivity enhancement in a sustainable manner.',
                'benefits': '• Financial assistance for seeds\n• Soil health management\n• Crop protection measures\n• Capacity building of farmers\n• Post-harvest management support',
                'eligibility': '• Farmers cultivating in NFSM-notified districts\n• Small and marginal farmers prioritized\n• Farmer Producer Organizations (FPOs)\n• Registered agricultural cooperatives',
                'application_process': '1. Visit nearest Agriculture Office\n2. Submit required documents\n3. Verification by district committee\n4. Approval and fund transfer through DBT',
                'website_url': 'https://nfsm.gov.in/',
                'icon': 'fas fa-wheat-alt'
            },
            {
                'name': 'Pradhan Mantri Fasal Bima Yojana (PMFBY)',
                'ministry': 'Agriculture & Farmers Welfare',
                'budget': Decimal('16000.00'),
                'category_slug': 'insurance-schemes',
                'description': 'PMFBY provides comprehensive crop insurance coverage against natural calamities, pests, and diseases to stabilize farmers\' income and encourage adoption of modern agricultural practices.',
                'benefits': '• Premium subsidy (upto 90% for small farmers)\n• Quick claim settlement\n• Coverage for prevented sowing\n• Post-harvest losses coverage\n• Localized calamity coverage',
                'eligibility': '• All farmers growing notified crops\n• Compulsory for loanee farmers\n• Voluntary for non-loanee farmers\n• Farmers with insurable interest in crop',
                'application_process': '1. Enroll through bank/insurance company\n2. Pay premium (subsidized rates)\n3. Insurance certificate issued\n4. Claim process activated on crop loss',
                'website_url': 'https://pmfby.gov.in/',
                'icon': 'fas fa-shield-alt'
            },
            {
                'name': 'PM-KISAN Samman Nidhi',
                'ministry': 'Agriculture & Farmers Welfare',
                'budget': Decimal('75000.00'),
                'category_slug': 'financial-assistance',
                'description': 'PM-KISAN is a central sector scheme to provide income support to all landholding farmers\' families across the country.',
                'benefits': '• ₹6,000 per year in three equal installments\n• Direct transfer to bank accounts\n• No intermediaries\n• Covers all farmer families',
                'eligibility': '• All landholding farmer families\n• Small and marginal farmers\n• Farmers irrespective of land size\n• Excludes institutional landholders',
                'application_process': '1. Register at Common Service Centre\n2. Submit land ownership documents\n3. Bank account verification\n4. Regular installment transfer',
                'website_url': 'https://pmkisan.gov.in/',
                'icon': 'fas fa-rupee-sign'
            },
            {
                'name': 'Paramparagat Krishi Vikas Yojana (PKVY)',
                'ministry': 'Agriculture & Farmers Welfare',
                'budget': Decimal('4500.00'),
                'category_slug': 'agricultural-schemes',
                'description': 'PKVY promotes organic farming through adoption of organic village by cluster approach and Participatory Guarantee System certification.',
                'benefits': '• Financial assistance of ₹50,000/ha\n• Certification support\n• Capacity building\n• Marketing support\n• Input procurement assistance',
                'eligibility': '• Farmers willing to adopt organic farming\n• Minimum group of 50 farmers\n• Cluster size of 50 acres\n• Commitment for 3 years',
                'application_process': '1. Form farmer group/cluster\n2. Submit proposal to district agriculture officer\n3. Technical approval\n4. Implementation through state agencies',
                'website_url': 'https://pgsindia-ncof.gov.in/pkvy.aspx',
                'icon': 'fas fa-leaf'
            }
        ]

        for scheme_data in schemes_data:
            category = SchemeCategory.objects.get(slug=scheme_data.pop('category_slug'))
            scheme, created = GovernmentScheme.objects.get_or_create(
                name=scheme_data['name'],
                defaults={
                    **scheme_data,
                    'category': category,
                    'slug': scheme_data['name'].lower().replace(' ', '-').replace('(', '').replace(')', ''),
                    'fiscal_year': 'FY2025-26',
                    'last_updated': timezone.now().date().replace(month=4, day=1),
                    'is_active': True,
                    'contact_info': 'Contact your nearest Agriculture Extension Office or visit agriculture.gov.in',
                    'documents_required': '• Aadhaar Card\n• Land ownership records\n• Bank account details\n• Passport size photograph'
                }
            )
            if created:
                self.stdout.write(f'Created scheme: {scheme.name}')

        self.stdout.write(self.style.SUCCESS('Successfully loaded sample schemes data'))