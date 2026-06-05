#!/usr/bin/env python3
"""Generate directory content via OpenRouter API."""
import os, sys, base64, requests, json
from pathlib import Path

def load_env():
    hermes_home = os.environ.get('HERMES_HOME', str(Path.home() / 'AppData' / 'Local' / 'hermes'))
    env_path = Path(hermes_home) / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
    return os.environ.get('OPENROUTER_API_KEY', '')

api_key = load_env()
if not api_key:
    print("No OPENROUTER_API_KEY found")
    sys.exit(1)

prompt = """You are building a directory website: 'Best Plumbers in Tucson, Arizona.'

Return ONLY valid JSON. No markdown, no code fences, no explanation. Just the JSON object.

The JSON must have these keys:
- site_title: string
- tagline: string
- plumbers: array of objects with {name, phone, address, description (3 sentences), rating (4.0-4.9), featured (bool, max 3 true)}
- city_guide_html: string (full HTML for a 500-word guide "How to Choose a Plumber in Tucson" — use <h2>, <p>, <ul>)
- blog_posts: array of {title, slug, content_html} (5 posts as listed below)
- meta_tags: array of {page, title, description}
- faq: array of {question, answer}

The 5 blog posts are:
1. "3 Signs Your Tucson Home Has Hard Water Damage" (slug: hard-water-damage)
2. "Emergency Plumber vs. Scheduled Repair: When to Call" (slug: emergency-vs-scheduled)
3. "How Monsoon Season Affects Your Plumbing in Tucson" (slug: monsoon-plumbing)
4. "Water Heater Maintenance for Arizona Homes" (slug: water-heater-maintenance)
5. "Tucson Pipe Repair: Copper vs. PEX" (slug: copper-vs-pex)

Phone numbers must be (520) area code. Addresses must be real-looking Tucson addresses.
Ratings between 4.0 and 4.9. Exactly 3 plumbers should have featured: true.

Now return the JSON."""

resp = requests.post(
    'https://openrouter.ai/api/v1/chat/completions',
    headers={
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    },
    json={
        'model': 'google/gemini-2.5-flash-lite',
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 8000,
        'temperature': 0.7
    },
    timeout=180
)

if resp.status_code != 200:
    print(f'Error: {resp.status_code} {resp.text[:500]}')
    sys.exit(1)

content = resp.json()['choices'][0]['message']['content']

# Try to extract JSON from the response (handle if it wraps in code fences)
content = content.strip()
if content.startswith('```'):
    # Extract from code fence
    lines = content.split('\n')
    start = 0
    for i, line in enumerate(lines):
        if line.startswith('```'):
            start = i + 1
            break
    end = len(lines)
    for i in range(len(lines)-1, start, -1):
        if lines[i].startswith('```'):
            end = i
            break
    content = '\n'.join(lines[start:end])

# Validate JSON
try:
    data = json.loads(content)
    print(f"VALID JSON: {len(data.get('plumbers', []))} plumbers, {len(data.get('blog_posts', []))} blog posts, {len(data.get('faq', []))} FAQ items")
    # Pretty print
    print(json.dumps(data, indent=2))
except json.JSONDecodeError as e:
    print(f"JSON parse error: {e}")
    print("Raw output:")
    print(content[:2000])
