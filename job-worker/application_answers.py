"""Resolve form answers only from explicit owner facts; never ask a model to invent them."""
import re


def answer_for(label, config):
    """None means unknown, including a skill-specific tenure or a new legal agreement."""
    label = re.sub(r'\s+', ' ', str(label)).strip().lower().rstrip(' *:')
    personal = config.get('personals', {})
    questions = config.get('questions', {})
    if re.search(r'agree|arbitration|terms|consent|certify|attest', label):
        return None
    exact = {
        'first name': personal.get('first_name'),
        'last name': personal.get('last_name'),
        'full name': ' '.join(filter(None, (personal.get('first_name'), personal.get('last_name')))),
        'email': personal.get('email') or personal.get('email_address'),
        'email address': personal.get('email') or personal.get('email_address'),
        'phone': personal.get('phone_number'),
        'phone number': personal.get('phone_number'),
        'mobile phone number': personal.get('phone_number'),
        'mobile number': personal.get('phone_number'),
        'city': personal.get('current_city'),
        'current city': personal.get('current_city'),
        'linkedin profile': questions.get('linkedIn'),
        'linkedin profile url': questions.get('linkedIn'),
        'website': questions.get('website'),
        'portfolio': questions.get('website'),
    }
    if label in exact:
        value = exact[label]
        return str(value) if value not in (None, '') else None
    if re.search(r'country.*code|dial(?:ing)? code', label):
        phone = str(personal.get('phone_number', '')).replace(' ', '')
        return '+971' if phone.startswith(('+971', '00971')) else None
    if re.search(r'(?:legally |legally.*)?authori[sz]ed to work|legal right to work', label):
        value = questions.get('legally_authorized')
        # A UAE answer cannot be reused for an overseas work-permit question.
        foreign = re.search(r'\b(?:usa|us|united states|canada|uk|united kingdom|europe|eu|saudi|qatar)\b', label)
        return value if not foreign and value in ('Yes', 'No') else None
    if re.search(r'requir.*sponsor|need.*sponsor|require.*visa', label):
        value = questions.get('require_visa')
        foreign = re.search(r'\b(?:usa|us|united states|canada|uk|united kingdom|europe|eu|saudi|qatar)\b', label)
        return value if not foreign and value in ('Yes', 'No') else None
    if re.fullmatch(r'(?:what is your )?notice period(?: \(days\)| in days)?\??', label):
        value = questions.get('notice_period')
        return str(value) if isinstance(value, (int, float)) and value >= 0 else None
    if re.fullmatch(r'(?:total years of (?:work |professional )?experience|how many years of (?:total |professional |work )?experience do you have)\??', label):
        value = questions.get('years_of_experience')
        return str(value) if value not in (None, '') else None
    # Salary zero is an unset sentinel, never an approved salary expectation.
    if label in ('desired salary', 'expected salary', 'expected annual salary'):
        value = questions.get('desired_salary')
        # Only a stored currency/period-specific answer is safe to transmit.
        approved = questions.get('salary_answer')
        return approved if value and isinstance(approved, str) and approved.strip() else None
    return None


def required_unknown(fields, config):
    """An unfamiliar prefilled value is not evidence that its answer is approved."""
    return [field.get('label') or 'Unlabelled required field' for field in fields
            if field.get('required') and field.get('type') != 'file'
            and answer_for(field.get('label', ''), config) is None]


def is_resume_field(field):
    label = ' '.join(str(field.get(key, '')) for key in ('label', 'question', 'originalId', 'name'))
    if re.search(r'cover.?letter|licen[sc]e|passport|identity|certificate|writing sample|portfolio', label, re.I):
        return False
    return bool(re.search(r'resume|\bcv\b|jobs-document-upload-file-upload', label, re.I))
