import re
from bs4 import BeautifulSoup

def clean_html_to_text(html_content: str) -> str:
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for element in soup(["script", "style", "head", "footer", "nav"]):
        element.extract()
        
    text = soup.get_text(separator=' ')
    return text

def normalize_email_body(plain_text: str, html_text: str = "") -> str:
    """Clean email text by removing signatures, footers, tracking links, and quoted replies."""
    raw_text = plain_text if plain_text and plain_text.strip() else clean_html_to_text(html_text)
    if not raw_text:
        return ""

    lines = raw_text.splitlines()
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Stop processing at common email quote markers
        if re.match(r'^(On\s.*wrote:|From:|Sent:|Subject:|>+)', stripped, re.IGNORECASE):
            break
        if re.match(r'^---+\s*Original Message\s*---+', stripped, re.IGNORECASE):
            break
        if re.match(r'^--\s*$', stripped): # Signature separator
            break
            
        # Ignore unsubscribe boilerplate and common marketing footers
        if re.search(r'unsubscribe|view in browser|privacy policy|terms of service|all rights reserved', stripped, re.IGNORECASE):
            continue
            
        if stripped:
            cleaned_lines.append(stripped)

    normalized = " ".join(cleaned_lines)
    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized
