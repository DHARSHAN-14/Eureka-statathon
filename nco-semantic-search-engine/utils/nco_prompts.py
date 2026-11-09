# Data-driven occupation prompts based on NCO dataset analysis
# Generated from actual occupation titles and categories found in the dataset

NCO_OCCUPATION_PROMPTS = {
    # Management (357 occupations) - Largest category
    'manager': [
        "The person who leads teams and coordinates business operations.",
        "I oversee projects and manage employee performance.",
        "I make strategic decisions to achieve organizational goals."
    ],
    'director': [
        "The person who directs organizational strategy and operations.",
        "I lead departments and set strategic direction.",
        "I work with senior management to drive business success."
    ],
    'executive': [
        "The person who manages high-level business operations.",
        "I make executive decisions and lead the organization.",
        "I work with board members and stakeholders."
    ],
    'chief': [
        "The person who heads major departments or functions.",
        "I lead specialized teams and oversee critical operations.",
        "I provide strategic guidance in my area of expertise."
    ],
    
    # Engineering (373 occupations) - Second largest
    'engineer': [
        "The person who designs and builds technical solutions.",
        "I work with complex systems and develop innovative products.",
        "I apply scientific principles to solve practical problems."
    ],
    'technician': [
        "The person who provides technical support and maintenance.",
        "I install, maintain, and repair technical equipment.",
        "I ensure systems operate efficiently and safely."
    ],
    'mechanic': [
        "The person who repairs and maintains machinery.",
        "I diagnose mechanical problems and perform repairs.",
        "I work with engines, tools, and mechanical systems."
    ],
    
    # Transportation (520 occupations) - Actually the largest!
    'operator': [
        "The person who operates machinery and equipment.",
        "I control machines and ensure proper operation.",
        "I work with industrial equipment and production systems."
    ],
    'driver': [
        "The person who operates vehicles for transportation.",
        "I drive cars, trucks, or buses to transport people or goods.",
        "I ensure safe and timely delivery of passengers or cargo."
    ],
    'conductor': [
        "The person who directs orchestras or transportation systems.",
        "I lead musical performances or coordinate transport operations.",
        "I ensure smooth execution of activities."
    ],
    
    # Administrative (170 occupations)
    'assistant': [
        "The person who provides administrative support and assistance.",
        "I help with office tasks and organizational activities.",
        "I support managers and teams with daily operations."
    ],
    'clerk': [
        "The person who handles administrative and record-keeping tasks.",
        "I manage documents, files, and office communications.",
        "I ensure proper documentation and office organization."
    ],
    'official': [
        "The person who holds official government or administrative positions.",
        "I work in government agencies and public administration.",
        "I implement policies and serve the public."
    ],
    
    # Services (193 occupations)
    'worker': [
        "The person who performs various service and support tasks.",
        "I provide essential services and support functions.",
        "I work in diverse service industries and roles."
    ],
    'attendant': [
        "The person who provides customer service and assistance.",
        "I help customers and ensure service quality.",
        "I work in service environments supporting clients."
    ],
    'guard': [
        "The person who provides security and protection.",
        "I ensure safety and security of people and property.",
        "I monitor activities and respond to security issues."
    ],
    
    # Sales/Marketing (81 occupations)
    'sales': [
        "The person who sells products and services to customers.",
        "I promote products and build customer relationships.",
        "I achieve sales targets and drive revenue growth."
    ],
    'marketing': [
        "The person who develops marketing strategies and campaigns.",
        "I create promotional materials and analyze markets.",
        "I work to increase brand awareness and sales."
    ],
    'agent': [
        "The person who represents companies and facilitates transactions.",
        "I work with clients and coordinate business activities.",
        "I provide specialized services and solutions."
    ],
    
    # Skilled Trades (68 occupations)
    'construction': [
        "The person who builds and constructs structures.",
        "I work on buildings, infrastructure, and construction projects.",
        "I ensure structural integrity and project completion."
    ],
    'maker': [
        "The person who creates and manufactures products.",
        "I produce goods and work with production processes.",
        "I craft items and ensure quality manufacturing."
    ],
    'hand': [
        "The person who performs manual and skilled work.",
        "I use tools and techniques to create and repair items.",
        "I work with my hands in various skilled trades."
    ],
    
    # Creative (72 occupations)
    'designer': [
        "The person who creates visual concepts and designs.",
        "I work with graphics, layouts, and visual communication.",
        "I develop designs for products, websites, and materials."
    ],
    'artist': [
        "The person who creates artistic works and expressions.",
        "I produce visual art and creative content.",
        "I express ideas through various artistic mediums."
    ],
    
    # IT/Technology (62 occupations)
    'analyst': [
        "The person who analyzes data and systems.",
        "I study information and provide insights and recommendations.",
        "I work with data analysis and system optimization."
    ],
    'system': [
        "The person who manages and maintains computer systems.",
        "I ensure systems operate efficiently and securely.",
        "I work with technology infrastructure and operations."
    ],
    
    # Science (45 occupations)
    'scientist': [
        "The person who conducts scientific research and experiments.",
        "I study natural phenomena and advance scientific knowledge.",
        "I work in laboratories and research environments."
    ],
    'physicist': [
        "The person who studies matter, energy, and physical phenomena.",
        "I conduct experiments and develop scientific theories.",
        "I work with fundamental principles of nature."
    ],
    'astronomer': [
        "The person who researches about stars and space.",
        "I study celestial objects and work at an observatory.",
        "I analyze astronomical data and teach about the universe."
    ],
    
    # Education (46 occupations)
    'teacher': [
        "The person who teaches students and helps them learn.",
        "I work in educational institutions and provide instruction.",
        "I specialize in teaching specific subjects and skills."
    ],
    'professor': [
        "The person who teaches at university level and conducts research.",
        "I lecture students and advance knowledge in my field.",
        "I publish academic work and mentor students."
    ],
    
    # Healthcare (55 occupations)
    'medical': [
        "The person who provides healthcare and medical services.",
        "I work with patients and provide medical treatment.",
        "I ensure health and wellbeing through medical care."
    ],
    'nursery': [
        "The person who cares for plants and manages nursery operations.",
        "I work with plant cultivation and nursery management.",
        "I ensure proper growth and care of plants."
    ],
    
    # Finance (51 occupations)
    'bank': [
        "The person who works in banking and financial services.",
        "I manage financial transactions and banking operations.",
        "I provide financial services to customers and clients."
    ],
    'accountant': [
        "The person who manages financial records and accounting.",
        "I prepare financial statements and ensure accuracy.",
        "I work with financial data and reporting systems."
    ],
    
    # Hospitality (30 occupations)
    'chef': [
        "The person who prepares food and creates culinary dishes.",
        "I work in kitchens designing menus and cooking meals.",
        "I manage food preparation and kitchen operations."
    ],
    'catering': [
        "The person who provides food services for events.",
        "I organize and execute catering services.",
        "I ensure quality food service for various occasions."
    ],
    
    # Agriculture (32 occupations)
    'farm': [
        "The person who manages agricultural operations and farming.",
        "I work with crops, livestock, and farm management.",
        "I ensure agricultural productivity and sustainability."
    ],
    'livestock': [
        "The person who cares for and manages animals.",
        "I work with livestock and animal husbandry.",
        "I ensure animal health and productivity."
    ],
    
    # Legal (16 occupations)
    'lawyer': [
        "The person who provides legal advice and representation.",
        "I represent clients in legal matters and proceedings.",
        "I specialize in specific areas of law and legal services."
    ],
    'advocate': [
        "The person who advocates for causes and represents interests.",
        "I work to promote and protect various rights and causes.",
        "I provide advocacy and representation services."
    ],
    
    # Default fallback
    'professional': [
        "The person who works in a specialized field with expertise.",
        "I apply my skills and knowledge to perform specific job duties.",
        "I contribute to organizational goals through professional work."
    ]
}

def get_nco_occupation_prompts(occupation_title):
    """Get well-defined prompts based on NCO occupation title analysis"""
    title_lower = occupation_title.lower()
    
    # Check for exact matches first (prioritize most specific)
    for key, prompts in NCO_OCCUPATION_PROMPTS.items():
        if key in title_lower:
            return prompts
    
    # Check for broader category matches based on dataset analysis
    if any(word in title_lower for word in ['manager', 'director', 'executive', 'chief']):
        return NCO_OCCUPATION_PROMPTS['manager']
    elif any(word in title_lower for word in ['engineer', 'technician', 'mechanic']):
        return NCO_OCCUPATION_PROMPTS['engineer']
    elif any(word in title_lower for word in ['operator', 'driver', 'conductor']):
        return NCO_OCCUPATION_PROMPTS['operator']
    elif any(word in title_lower for word in ['assistant', 'clerk', 'official']):
        return NCO_OCCUPATION_PROMPTS['assistant']
    elif any(word in title_lower for word in ['worker', 'attendant', 'guard']):
        return NCO_OCCUPATION_PROMPTS['worker']
    elif any(word in title_lower for word in ['sales', 'marketing', 'agent']):
        return NCO_OCCUPATION_PROMPTS['sales']
    elif any(word in title_lower for word in ['construction', 'maker', 'hand']):
        return NCO_OCCUPATION_PROMPTS['construction']
    elif any(word in title_lower for word in ['designer', 'artist']):
        return NCO_OCCUPATION_PROMPTS['designer']
    elif any(word in title_lower for word in ['analyst', 'system']):
        return NCO_OCCUPATION_PROMPTS['analyst']
    elif any(word in title_lower for word in ['scientist', 'physicist', 'astronomer']):
        return NCO_OCCUPATION_PROMPTS['scientist']
    elif any(word in title_lower for word in ['teacher', 'professor']):
        return NCO_OCCUPATION_PROMPTS['teacher']
    elif any(word in title_lower for word in ['medical', 'nursery']):
        return NCO_OCCUPATION_PROMPTS['medical']
    elif any(word in title_lower for word in ['bank', 'accountant']):
        return NCO_OCCUPATION_PROMPTS['bank']
    elif any(word in title_lower for word in ['chef', 'catering']):
        return NCO_OCCUPATION_PROMPTS['chef']
    elif any(word in title_lower for word in ['farm', 'livestock']):
        return NCO_OCCUPATION_PROMPTS['farm']
    elif any(word in title_lower for word in ['lawyer', 'advocate']):
        return NCO_OCCUPATION_PROMPTS['lawyer']
    
    # Default fallback
    return NCO_OCCUPATION_PROMPTS['professional']
