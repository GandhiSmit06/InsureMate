import urllib.request
import json

claim_id = 'CLM-E31E57D3'
questions = [
    'What is the verdict?',
    'What documents are missing?',
    'What are the coverage dates?',
    'Who is the patient?',
    'What is the total bill amount?',
    'What is the treating hospital?',
    'What is the diagnosis?',
    'Summarize this claim'
]

for q in questions:
    req = urllib.request.Request(
        f'http://127.0.0.1:8000/api/claims/{claim_id}/assistant',
        data=json.dumps({'question': q}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f'Q: {q}')
            print(f'A: {data["answer"]}')
            print('---')
    except Exception as e:
        print(f'Q: {q} FAILED: {e}')
