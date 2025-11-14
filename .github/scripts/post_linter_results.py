#!/usr/bin/env python3
"""
Postitab Super Linter'i tulemused PR'i kommentaaridena
"""
import os
import sys
import json
import requests
import re
from pathlib import Path

def parse_super_linter_logs():
    """Parsib Super Linter'i logid ja leiab vead"""
    errors = []
    
    # Super Linter loob logi faile /github/workspace/super-linter.log
    log_paths = [
        '/github/workspace/super-linter.log',
        'super-linter.log',
        '/tmp/lint/super-linter.log'
    ]
    
    # Proovime leida logi faile
    for log_path in log_paths:
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    content = f.read()
                    # Parsime vigu
                    # Näide: ./client/src/App.js:10:5: error: Expected semicolon
                    pattern = r'(.+?):(\d+):(\d+):\s*(error|warning):\s*(.+)'
                    for match in re.finditer(pattern, content):
                        file_path = match.group(1).strip()
                        line = int(match.group(2))
                        column = int(match.group(3))
                        severity = match.group(4)
                        message = match.group(5).strip()
                        
                        errors.append({
                            'file': file_path,
                            'line': line,
                            'column': column,
                            'severity': severity,
                            'message': message
                        })
            except Exception as e:
                print(f"Error reading log file {log_path}: {e}", file=sys.stderr)
    
    return errors

def post_review_comments(errors):
    """Postitab review kommentaarid PR'i"""
    github_token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY')
    pr_number = os.environ.get('PR_NUMBER')
    
    if not all([github_token, repo, pr_number]):
        print("Puuduvad vajalikud keskkonna muutujad", file=sys.stderr)
        return False
    
    if not errors:
        print("Vigu ei leitud")
        return True
    
    # Grupeerime vead failide kaupa
    files_with_errors = {}
    for error in errors:
        file_path = error['file']
        if file_path not in files_with_errors:
            files_with_errors[file_path] = []
        files_with_errors[file_path].append(error)
    
    # Loome kommentaarid PR'i
    comments = []
    for file_path, file_errors in files_with_errors.items():
        for error in file_errors:
            severity_icon = "🔴" if error['severity'] == 'error' else "⚠️"
            severity_text = "HARD" if error['severity'] == 'error' else "MEDIUM"
            
            comment_body = f"{severity_icon} **{severity_text}**: {error['message']}"
            
            comments.append({
                'path': file_path.lstrip('./'),
                'line': error['line'],
                'body': comment_body
            })
    
    # Postitame review kommentaarid
    try:
        # Loome PR review
        response = requests.post(
            f'https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews',
            headers={
                'Authorization': f'Bearer {github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'X-GitHub-Api-Version': '2022-11-28'
            },
            json={
                'body': f'## 🔍 Super Linter tulemused\n\nLeitud {len(errors)} tähelepanekut.',
                'event': 'COMMENT',
                'comments': comments
            },
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ Postitatud {len(comments)} kommentaari PR'i")
            return True
        else:
            print(f"❌ GitHub API error: {response.status_code} - {response.text}", file=sys.stderr)
            return False
            
    except Exception as e:
        print(f"Error posting review: {e}", file=sys.stderr)
        return False

def post_summary_comment(errors):
    """Postitab kokkuvõtte kommentaari PR'i"""
    github_token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY')
    pr_number = os.environ.get('PR_NUMBER')
    
    if not all([github_token, repo, pr_number]):
        return False
    
    if not errors:
        comment = """## GitHub Super Linter - Tulemused

✅ **Kontroll läbitud edukalt!**

- ✅ Medium tähelepanekuid ei leitud
- ✅ Hard tähelepanekuid ei leitud
- ✅ Koodikvaliteet on korras

*Kontrollitud: JavaScript, JSON, YAML, Docker, Markdown*"""
    else:
        error_count = sum(1 for e in errors if e['severity'] == 'error')
        warning_count = sum(1 for e in errors if e['severity'] == 'warning')
        
        comment = f"""## 🔍 GitHub Super Linter - Tulemused

⚠️ **Leitud {len(errors)} tähelepanekut:**

- 🔴 **Hard tähelepanekuid: {error_count}**
- ⚠️ **Medium tähelepanekuid: {warning_count}**

Vaata kommentaare koodi juures täpsemate detailide jaoks.

*Kontrollitud: JavaScript, JSON, YAML, Docker, Markdown*"""
    
    try:
        response = requests.post(
            f'https://api.github.com/repos/{repo}/issues/{pr_number}/comments',
            headers={
                'Authorization': f'Bearer {github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'X-GitHub-Api-Version': '2022-11-28'
            },
            json={'body': comment},
            timeout=10
        )
        
        return response.status_code == 201
    except Exception as e:
        print(f"Error posting summary: {e}", file=sys.stderr)
        return False

def main():
    """Peamine funktsioon"""
    print("Parsin Super Linter'i tulemusi...")
    errors = parse_super_linter_logs()
    
    print(f"Leitud {len(errors)} tähelepanekut")
    
    # Postitame review kommentaarid (kui on vigu)
    if errors:
        print("Postitan review kommentaarid...")
        post_review_comments(errors)
    
    # Postitame kokkuvõtte
    print("Postitan kokkuvõtte...")
    post_summary_comment(errors)
    
    print("✅ Valmis!")

if __name__ == '__main__':
    main()

