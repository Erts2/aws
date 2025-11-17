#!/usr/bin/env python3
"""
AI töömahu hinnang PR'i jaoks
"""
import os
import sys
import subprocess
import json
import requests

def get_pr_changes():
    """Saab PR muudatuste info"""
    base_ref = os.environ.get('GITHUB_BASE_REF', 'main')
    head_ref = os.environ.get('GITHUB_HEAD_REF', '')
    
    if not head_ref:
        # Kui pole PR, siis võrdle praegust branch'i main'iga
        head_ref = os.environ.get('GITHUB_REF', '').replace('refs/heads/', '')
    
    try:
        # Loendame muudetud failid
        result = subprocess.run(
            ['git', 'diff', '--stat', f'origin/{base_ref}...HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Loendame lisatud/kustutatud read
        diff_result = subprocess.run(
            ['git', 'diff', '--shortstat', f'origin/{base_ref}...HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Loendame failid
        files_result = subprocess.run(
            ['git', 'diff', '--name-only', f'origin/{base_ref}...HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        
        changed_files = files_result.stdout.strip().split('\n') if files_result.stdout.strip() else []
        
        return {
            'stat': result.stdout,
            'shortstat': diff_result.stdout,
            'files': changed_files,
            'file_count': len(changed_files)
        }
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}", file=sys.stderr)
        return None

def analyze_with_ai(changes_info):
    """Analüüsib muudatused AI abil"""
    openai_api_key = os.environ.get('OPENAI_API_KEY')
    
    if not openai_api_key:
        print("OPENAI_API_KEY pole seadistatud", file=sys.stderr)
        return None
    
    # Koostame prompt'i
    files_summary = f"Muudetud failide arv: {changes_info['file_count']}"
    if changes_info['files']:
        files_summary += f"\nFailid: {', '.join(changes_info['files'][:10])}"
        if len(changes_info['files']) > 10:
            files_summary += f" ... ja veel {len(changes_info['files']) - 10} faili"
    
    prompt = f"""Oled kogemuslik arendaja (3-4 aastat kogemust), kes hindab pull request'i töömahku.

PR muudatused:
{changes_info['stat']}
{changes_info['shortstat']}

{files_summary}

Hinda, kui palju töötunde võis kuluda keskmisel arendajal (3-4a kogemust) sellise koodi kirjutamiseks, arvestades:
- Nõuetega tutvumise aeg
- Funktsionaalsuse planeerimine ja disain
- Koodi kirjutamine
- Testide kirjutamine
- Dokumenteerimine
- Code review'de parandused
- Debugging ja veaotsing
- Kogu arendusprotsessi aeg

Anna vastus ainult numbri kujul (täisarv või kümnendkoht), mis tähistab töötunde.
Näide: "12.5" või "8"

Vastus:"""
    
    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {openai_api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o-mini',
                'messages': [
                    {
                        'role': 'system',
                        'content': 'Oled kogemuslik arendaja, kes hindab pull request\'ide töömahku. Anna vastus ainult numbri kujul (täisarv või kümnendkoht).'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.3,
                'max_tokens': 50
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            hours = result['choices'][0]['message']['content'].strip()
            # Eemaldame mittenumbrilised sümbolid
            hours = ''.join(c for c in hours if c.isdigit() or c == '.' or c == ',')
            hours = hours.replace(',', '.')
            return float(hours) if hours else None
        else:
            print(f"OpenAI API error: {response.status_code} - {response.text}", file=sys.stderr)
            return None
            
    except Exception as e:
        print(f"Error calling OpenAI API: {e}", file=sys.stderr)
        return None

def post_comment_to_pr(hours):
    """Postitab kommentaari PR'i"""
    github_token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY')
    pr_number = os.environ.get('GITHUB_EVENT_PATH')
    
    if not github_token or not repo:
        print("GITHUB_TOKEN või GITHUB_REPOSITORY pole seadistatud", file=sys.stderr)
        return False
    
    # Loeme PR numbri event failist
    try:
        with open(pr_number, 'r') as f:
            event_data = json.load(f)
            pr_num = event_data.get('pull_request', {}).get('number')
    except:
        # Kui pole PR event, siis ei postita
        print("Pole PR event", file=sys.stderr)
        return False
    
    if not pr_num:
        return False
    
    comment = f"""## 🤖 AI töömahu hinnang

**AI hinnangul võis kuluda: {hours} töötundi**

*Hinnang põhineb PR muudatustel ja arvestab:*
- Nõuetega tutvumise aeg
- Funktsionaalsuse planeerimine ja disain  
- Koodi kirjutamine
- Testide kirjutamine
- Dokumenteerimine
- Code review'de parandused
- Debugging ja veaotsing
- Kogu arendusprotsessi aeg

*Hinnang on tehtud keskmise arendaja (3-4a kogemust) perspektiivist.*
"""
    
    try:
        response = requests.post(
            f'https://api.github.com/repos/{repo}/issues/{pr_num}/comments',
            headers={
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github.v3+json'
            },
            json={'body': comment},
            timeout=10
        )
        
        if response.status_code == 201:
            print(f"Kommentaar postitatud PR #{pr_num}")
            return True
        else:
            print(f"GitHub API error: {response.status_code} - {response.text}", file=sys.stderr)
            return False
            
    except Exception as e:
        print(f"Error posting comment: {e}", file=sys.stderr)
        return False

def main():
    """Peamine funktsioon"""
    print("Analüüsin PR muudatusi...")
    changes_info = get_pr_changes()
    
    if not changes_info:
        print("Ei saanud PR muudatusi", file=sys.stderr)
        sys.exit(1)
    
    print(f"Leitud {changes_info['file_count']} muudetud faili")
    
    # Kontrollime, kas OPENAI_API_KEY on seadistatud
    if not os.environ.get('OPENAI_API_KEY'):
        print("⚠️ OPENAI_API_KEY pole seadistatud - jätan AI hinnangu vahele", file=sys.stderr)
        print("Postitan kommentaari ilma AI hinnanguta...")
        comment = """## 🤖 AI Töömahu Hinnang

⚠️ **AI hinnang pole saadaval** - OPENAI_API_KEY pole seadistatud GitHub secrets'is.

Palun lisa `OPENAI_API_KEY` GitHub'i Settings → Secrets and variables → Actions.
"""
        if post_comment_to_pr(comment):
            print("✅ Kommenteeritud (ilma hinnanguta)")
        sys.exit(0)
    
    print("Hindan töömahku AI abil...")
    hours = analyze_with_ai(changes_info)
    
    if not hours:
        print("⚠️ Ei saanud AI hinnangut", file=sys.stderr)
        # Proovime siiski kommenteerida
        comment = """## 🤖 AI Töömahu Hinnang

⚠️ **AI hinnang ebaõnnestus** - ei saanud hinnangut OpenAI API'st.

Võimalikud põhjused:
- OpenAI API viga
- API limiit ületatud
- Võrguprobleemid
"""
        if post_comment_to_pr(comment):
            print("✅ Kommenteeritud (veateade)")
        sys.exit(0)
    
    print(f"AI hinnang: {hours} töötundi")
    
    print("Postitan kommentaari PR'i...")
    if post_comment_to_pr(hours):
        print("✅ Valmis! Kommentaar postitatud.")
        sys.exit(0)
    else:
        print("⚠️ Kommentaari postitamine ebaõnnestus", file=sys.stderr)
        # Ei tee exit 1, sest hinnang on saadud
        sys.exit(0)

if __name__ == '__main__':
    main()

