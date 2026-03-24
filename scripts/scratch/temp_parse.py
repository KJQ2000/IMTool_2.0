import urllib.request
from html.parser import HTMLParser
import json

class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        if tag in ['input', 'select', 'textarea']:
            attr_dict = dict(attrs)
            name = attr_dict.get('name', attr_dict.get('id', 'unknown'))
            if name != 'unknown':
                rules = {
                    'tag': tag,
                    'type': attr_dict.get('type'),
                    'required': 'required' in attr_dict,
                    'min': attr_dict.get('min'),
                    'max': attr_dict.get('max'),
                    'step': attr_dict.get('step'),
                    'maxlength': attr_dict.get('maxlength')
                }
                # Remove None values
                rules = {k: v for k, v in rules.items() if v is not None and v is not False}
                self.inputs.append({name: rules})

urls = [
    'https://raw.githubusercontent.com/KJQ2000/IMtool/main/IMtool%20app/website/templates/addstocks.html',
    'https://raw.githubusercontent.com/KJQ2000/IMtool/main/IMtool%20app/website/templates/addsales.html',
    'https://raw.githubusercontent.com/KJQ2000/IMtool/main/IMtool%20app/website/templates/addpurchases.html',
    'https://raw.githubusercontent.com/KJQ2000/IMtool/main/IMtool%20app/website/templates/addbookings.html',
    'https://raw.githubusercontent.com/KJQ2000/IMtool/main/IMtool%20app/website/templates/addcustomers.html',
    'https://raw.githubusercontent.com/KJQ2000/IMtool/main/IMtool%20app/website/templates/addsalesmen.html'
]

all_rules = {}
for url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read().decode('utf-8')
        parser = FormParser()
        parser.feed(html)
        filename = url.split('/')[-1]
        all_rules[filename] = parser.inputs
    except Exception as e:
        all_rules[url.split('/')[-1]] = f"Error: {e}"

print(json.dumps(all_rules, indent=2))
