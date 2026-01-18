import pgeocode
import usaddress
from datetime import date
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta

import phonenumbers
from phonenumbers import geocoder

# Initialize for US and Canada
us = pgeocode.Nominatim('us')
ca = pgeocode.Nominatim('ca')


def validate_address(postal_code, state_province, country='auto'):
    """Validate postal/zip code and state/province"""

    # Auto-detect country
    if country == 'auto':
        country = 'ca' if any(c.isalpha() for c in postal_code) else 'us'

    geo = us if country.lower() == 'us' else ca
    result = geo.query_postal_code(postal_code)

    if result.empty or str(result['state_code']) == 'nan':
        return {'valid': False, 'error': 'Invalid postal code', "outcome": False}

    matches = result['state_code'] == state_province.upper()

    return {
        'valid': matches,
        'postal_code': postal_code,
        'expected_state': result['state_code'],
        'provided_state': state_province.upper(),
        'city': result['place_name'],
        'country': country.upper(),
        'outcome': True
    }

def parse_address(address_str):
    parts, type = usaddress.tag(address_str)
    return validate_address(parts["ZipCode"], parts["StateName"], country='auto')


def validate_dob(date_of_birth_d, date_of_birth_m, date_of_birth_y, min_age=0, max_age=150):
    """Validate DOB with flexible input handling."""
    try:
        # Handle string or int inputs
        dob = parse(f"{date_of_birth_y}-{date_of_birth_m}-{date_of_birth_d}").date()
        today = date.today()

        if dob > today:
            return {'valid': False, 'error': 'Future date'}

        age = relativedelta(today, dob).years

        if not (min_age <= age <= max_age):
            return {'valid': False, 'error': f'Age {age} out of range ({min_age}-{max_age})'}

        return {'valid': True, 'date': dob, 'age': age}

    except Exception:
        return {'valid': False, 'error': 'Invalid date'}



def validate_area_code(country_code, area_code):
    # We create a dummy number using the area code
    test_number = f"+{country_code}{area_code}5551212"
    try:
        parsed_num = phonenumbers.parse(test_number)

        # Check if the number is possible and has a valid location
        if phonenumbers.is_possible_number(parsed_num):
            location = geocoder.description_for_number(parsed_num, "en")
            return location if location else "Invalid Area Code"
        return "Invalid Format"
    except:
        return "Error"
