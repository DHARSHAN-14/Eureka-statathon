import json
import re
import os
from collections import Counter

# Load the metadata to analyze occupation titles
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_path = os.path.join(script_dir, 'data', 'processed', 'nco_metadata.json')
with open(data_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

occupation_titles = [item['occupation_title'] for item in metadata]

# Dynamic prompt generation templates based on occupation patterns
PROMPT_TEMPLATES = {
    # Leadership roles
    'leadership': [
        "The person who leads and directs {domain} operations.",
        "I oversee {domain} activities and make strategic decisions.",
        "I manage teams and ensure success in {domain}."
    ],
    
    # Technical/Engineering roles
    'technical': [
        "The person who works with {technical_domain} and technical systems.",
        "I apply technical expertise in {technical_domain}.",
        "I ensure proper operation and maintenance of {technical_domain}."
    ],
    
    # Service/Support roles
    'service': [
        "The person who provides {service_type} and support services.",
        "I assist with {service_type} and customer needs.",
        "I ensure quality {service_type} and client satisfaction."
    ],
    
    # Creative/Design roles
    'creative': [
        "The person who creates and designs {creative_domain}.",
        "I work with {creative_domain} and creative solutions.",
        "I develop innovative {creative_domain} and artistic content."
    ],
    
    # Educational roles
    'education': [
        "The person who teaches and educates in {education_domain}.",
        "I provide instruction and guidance in {education_domain}.",
        "I help students learn and develop in {education_domain}."
    ],
    
    # Healthcare roles
    'healthcare': [
        "The person who provides {healthcare_type} and medical care.",
        "I work with patients and deliver {healthcare_type}.",
        "I ensure health and wellbeing through {healthcare_type}."
    ],
    
    # Financial roles
    'financial': [
        "The person who manages {financial_domain} and financial operations.",
        "I handle {financial_domain} and financial transactions.",
        "I ensure proper {financial_domain} and financial management."
    ],
    
    # Production/Manufacturing roles
    'production': [
        "The person who produces and manufactures {product_type}.",
        "I work with {product_type} production processes.",
        "I ensure quality {product_type} and manufacturing efficiency."
    ],
    
    # Transportation roles
    'transportation': [
        "I drive or operate {transport_type}.",
        "My job is related to {transport_type}.",
        "I help transport people or goods using {transport_type}."
    ],
    
    # Administrative roles
    'administrative': [
        "The person who handles {admin_type} and administrative tasks.",
        "I manage {admin_type} and office operations.",
        "I ensure proper {admin_type} and organizational support."
    ],
    
    # Sales/Marketing roles
    'sales': [
        "The person who sells and promotes {product_service}.",
        "I work with {product_service} sales and marketing.",
        "I drive revenue through {product_service}."
    ],
    
    # Legal roles
    'legal': [
        "The person who provides {legal_type} and legal services.",
        "I handle {legal_type} and legal matters.",
        "I ensure compliance and proper {legal_type}."
    ],
    
    # Agricultural roles
    'agricultural': [
        "The person who works with {agri_type} and agricultural operations.",
        "I manage {agri_type} and farming activities.",
        "I ensure productive {agri_type} and agricultural success."
    ],
    
    # Research/Science roles
    'research': [
        "I study {research_domain}.",
        "I observe and record information about {research_domain}.",
        "My work is related to research on {research_domain}."
    ],
    
    # General worker roles
    'worker': [
        "I work as a {work_type}.",
        "My job is related to {work_type}.",
        "I do daily work connected with {work_type}."
    ]
}

def extract_domain_from_title(occupation_title):
    """Extract the main domain/area from occupation title"""
    title_lower = re.sub(r"[^a-z0-9\s]", " ", occupation_title.lower())
    
    # Remove common prefixes and suffixes
    prefixes = ['general', 'senior', 'junior', 'assistant', 'associate', 'chief', 'head', 'lead']
    suffixes = ['others', 'assistant', 'helper', 'worker', 'operator', 'attendant']
    
    words = title_lower.split()
    # Filter out common prefixes/suffixes
    filtered_words = [w for w in words if w not in prefixes + suffixes]
    
    # Extract key domain words
    domain_words = []
    for i, word in enumerate(filtered_words):
        # Skip very common words
        if word in ['and', 'of', 'in', 'for', 'with', 'or', 'the', 'a', 'an']:
            continue
        
        # Look for domain indicators
        if word in ['bank', 'financial', 'account', 'finance']:
            domain_words.append('banking and financial services')
        elif word in ['engineer', 'engineering', 'technical', 'mechanical']:
            domain_words.append('engineering and technical systems')
        elif word in ['medical', 'health', 'nurse', 'doctor']:
            domain_words.append('healthcare and medical services')
        elif word in ['teacher', 'education', 'professor', 'school']:
            domain_words.append('education and teaching')
        elif word in ['sales', 'marketing', 'promotion']:
            domain_words.append('sales and marketing')
        elif word in ['construction', 'building', 'infrastructure']:
            domain_words.append('construction and infrastructure')
        elif word in ['transport', 'driver', 'operator', 'vehicle']:
            domain_words.append('transportation and logistics')
        elif word in ['legal', 'law', 'court', 'advocate']:
            domain_words.append('legal services and compliance')
        elif word in ['farm', 'agricultural', 'crop', 'livestock']:
            domain_words.append('agricultural and farming operations')
        elif word in ['astronomer', 'astronomy', 'planet', 'star']:
            domain_words.append('stars, planets, and space')
        elif word in ['research', 'science', 'scientist', 'laboratory']:
            domain_words.append('research and scientific analysis')
        elif word in ['computer', 'software', 'system', 'it', 'network']:
            domain_words.append('information technology and systems')
        elif word in ['manufacturing', 'production', 'factory']:
            domain_words.append('manufacturing and production')
        elif word in ['hotel', 'restaurant', 'food', 'catering']:
            domain_words.append('hospitality and food services')
        elif len(word) > 3:  # Include meaningful words
            domain_words.append(word)
    
    # Return the most relevant domain
    if domain_words:
        return domain_words[0] if len(domain_words) == 1 else f"{' and '.join(domain_words[:2])}"
    return 'professional operations'

def determine_category(occupation_title):
    """Determine the category of occupation based on title patterns"""
    title_lower = occupation_title.lower()
    
    # Leadership indicators
    if any(word in title_lower for word in ['manager', 'director', 'executive', 'chief', 'head', 'lead', 'supervisor']):
        return 'leadership'
    
    # Technical/Engineering indicators
    elif any(word in title_lower for word in ['engineer', 'technician', 'mechanic', 'electrician', 'maintenance', 'technical']):
        return 'technical'
    
    # Healthcare indicators
    elif any(word in title_lower for word in ['doctor', 'nurse', 'medical', 'physician', 'surgeon', 'pharmacist', 'health']):
        return 'healthcare'
    
    # Education indicators
    elif any(word in title_lower for word in ['teacher', 'professor', 'education', 'lecturer', 'tutor']):
        return 'education'
    
    # Financial indicators
    elif any(word in title_lower for word in ['accountant', 'financial', 'bank', 'cashier', 'auditor']):
        return 'financial'
    
    # Sales/Marketing indicators
    elif any(word in title_lower for word in ['sales', 'marketing', 'agent', 'representative', 'promoter']):
        return 'sales'
    
    # Creative/Design indicators
    elif any(word in title_lower for word in ['designer', 'artist', 'creative', 'writer', 'photographer']):
        return 'creative'
    
    # Production/Manufacturing indicators
    elif any(word in title_lower for word in ['production', 'manufacturing', 'factory', 'maker', 'machine']):
        return 'production'
    
    # Transportation indicators
    elif any(word in title_lower for word in ['driver', 'operator', 'pilot', 'captain', 'transport']):
        return 'transportation'
    
    # Administrative indicators
    elif any(word in title_lower for word in ['assistant', 'clerk', 'secretary', 'administrative', 'official']):
        return 'administrative'
    
    # Legal indicators
    elif any(word in title_lower for word in ['lawyer', 'attorney', 'legal', 'advocate', 'judge']):
        return 'legal'
    
    # Agricultural indicators
    elif any(word in title_lower for word in ['farmer', 'agricultural', 'farm', 'livestock', 'crop']):
        return 'agricultural'
    
    # Research/Science indicators
    elif any(word in title_lower for word in ['scientist', 'researcher', 'physicist', 'chemist', 'biologist', 'astronomer', 'astronomy']):
        return 'research'
    
    # Service indicators
    elif any(word in title_lower for word in ['worker', 'helper', 'attendant', 'guard', 'service']):
        return 'service'
    
    # Default to worker category
    else:
        return 'worker'

def generate_dynamic_prompts(occupation_title):
    """Generate dynamic well-defined prompts for any occupation"""
    category = determine_category(occupation_title)
    domain = extract_domain_from_title(occupation_title)
    
    templates = PROMPT_TEMPLATES.get(category, PROMPT_TEMPLATES['worker'])
    
    # Generate prompts by filling templates
    prompts = []
    for template in templates:
        # Replace placeholders with actual domain
        if '{domain}' in template:
            prompt = template.format(domain=domain)
        elif '{technical_domain}' in template:
            prompt = template.format(technical_domain=domain)
        elif '{service_type}' in template:
            prompt = template.format(service_type=domain)
        elif '{creative_domain}' in template:
            prompt = template.format(creative_domain=domain)
        elif '{education_domain}' in template:
            prompt = template.format(education_domain=domain)
        elif '{healthcare_type}' in template:
            prompt = template.format(healthcare_type=domain)
        elif '{financial_domain}' in template:
            prompt = template.format(financial_domain=domain)
        elif '{product_type}' in template:
            prompt = template.format(product_type=domain)
        elif '{transport_type}' in template:
            prompt = template.format(transport_type=domain)
        elif '{admin_type}' in template:
            prompt = template.format(admin_type=domain)
        elif '{product_service}' in template:
            prompt = template.format(product_service=domain)
        elif '{legal_type}' in template:
            prompt = template.format(legal_type=domain)
        elif '{agri_type}' in template:
            prompt = template.format(agri_type=domain)
        elif '{research_domain}' in template:
            prompt = template.format(research_domain=domain)
        elif '{work_type}' in template:
            prompt = template.format(work_type=domain)
        else:
            prompt = template
        
        prompts.append(prompt)
    
    return prompts

# Test the system with some examples
if __name__ == "__main__":
    test_occupations = [
        "Finance Managers, Others",
        "General Manager, Bank", 
        "Physicist, Mechanics",
        "Automated Optical Inspection Machine Operator",
        "University and College Teacher, Law",
        "Executive Chef",
        "Working Proprietor, Construction",
        "Attorney at Law",
        "Solar Energy System Designer",
        "Agricultural and Forestry Production Managers, Others"
    ]
    
    print("Testing Dynamic Prompt Generation:")
    print("=" * 50)
    
    for occupation in test_occupations:
        print(f"\nOccupation: {occupation}")
        print(f"Category: {determine_category(occupation)}")
        print(f"Domain: {extract_domain_from_title(occupation)}")
        prompts = generate_dynamic_prompts(occupation)
        for i, prompt in enumerate(prompts, 1):
            print(f"  {i}. {prompt}")
        print()
