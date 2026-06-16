import json
import re
import os
from collections import Counter

# Load the metadata to analyze occupation titles
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_path = os.path.join(script_dir, 'data', 'processed', 'nco_metadata.json')
with open(data_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

print(f'Total occupations: {len(metadata)}')

# Extract unique occupation titles
occupation_titles = [item['occupation_title'] for item in metadata]
print(f'Unique titles: {len(set(occupation_titles))}')

# Show some sample titles
print('\nSample occupation titles:')
for i, title in enumerate(occupation_titles[:20]):
    print(f'{i+1:2d}. {title}')

# Analyze common keywords
all_words = []
for title in occupation_titles:
    words = re.findall(r'\b\w+\b', title.lower())
    all_words.extend(words)

word_freq = Counter(all_words)
print('\nMost common words in occupation titles:')
for word, count in word_freq.most_common(30):
    if word not in ['and', 'of', 'others', 'assistant', 'i', 'ii', 'iii', 'iv']:
        print(f'{word}: {count}')

# Group occupations by major categories
categories = {
    'Management': ['manager', 'director', 'chief', 'executive', 'head', 'supervisor', 'lead'],
    'Engineering': ['engineer', 'technician', 'mechanic', 'electrician', 'maintenance'],
    'Healthcare': ['doctor', 'nurse', 'medical', 'physician', 'surgeon', 'pharmacist', 'therapist'],
    'Education': ['teacher', 'professor', 'lecturer', 'tutor', 'educator', 'trainer'],
    'Finance': ['accountant', 'financial', 'bank', 'cashier', 'clerk', 'auditor'],
    'IT/Technology': ['software', 'developer', 'programmer', 'analyst', 'system', 'network'],
    'Sales/Marketing': ['sales', 'marketing', 'agent', 'representative', 'promoter'],
    'Administrative': ['assistant', 'clerk', 'secretary', 'administrative', 'office'],
    'Skilled Trades': ['carpenter', 'plumber', 'welder', 'painter', 'mason', 'construction'],
    'Transportation': ['driver', 'operator', 'pilot', 'captain', 'conductor'],
    'Hospitality': ['waiter', 'chef', 'cook', 'hotel', 'restaurant', 'catering'],
    'Agriculture': ['farmer', 'agricultural', 'horticulture', 'livestock', 'crop'],
    'Legal': ['lawyer', 'attorney', 'legal', 'judge', 'advocate'],
    'Creative': ['artist', 'designer', 'writer', 'photographer', 'musician', 'actor'],
    'Science': ['scientist', 'researcher', 'chemist', 'physicist', 'biologist', 'geologist'],
    'Services': ['worker', 'helper', 'attendant', 'guard', 'cleaner', 'security']
}

print('\nOccupation categories found:')
category_counts = {}
for category, keywords in categories.items():
    count = 0
    sample_jobs = []
    for title in occupation_titles:
        title_lower = title.lower()
        if any(keyword in title_lower for keyword in keywords):
            count += 1
            if len(sample_jobs) < 3:
                sample_jobs.append(title)
    
    category_counts[category] = count
    print(f'\n{category}: {count} occupations')
    for job in sample_jobs:
        print(f'  - {job}')

print(f'\nTotal categorized: {sum(category_counts.values())}')
print(f'Uncategorized: {len(occupation_titles) - sum(category_counts.values())}')
