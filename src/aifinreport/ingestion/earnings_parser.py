# Create new parser
# src/aifinreport/ingestion/earnings_parser.py
"""
Parse earnings call transcripts with clean structure.
"""
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta


def parse_transcript_file(file_path: Path, call_start_utc: datetime) -> Dict[str, Any]:
    """
    Parse structured earnings call transcript.
    
    Expected format:
    ---INTERVENTION--- or ---Q&A---
    SPEAKER/ANALYST: name
    ROLE: role (optional)
    TIME: 0:00:00
    TEXT/QUESTION/ANSWER: content
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    interventions = []
    sequence = 1
    
    # Split by separators
    blocks = content.split('---INTERVENTION---')[1:]  # Skip empty first element
    qa_blocks = content.split('---Q&A---')[1:] if '---Q&A---' in content else []
    
    # Parse interventions
    for block in blocks:
        if not block.strip() or '---Q&A---' in block:
            continue
        
        intervention = parse_intervention_block(block.strip(), call_start_utc, sequence, False)
        if intervention:
            interventions.append(intervention)
            sequence += 1
    
    # Parse Q&A
    for qa_block in qa_blocks:
        if not qa_block.strip():
            continue
        
        # Q&A can have multiple parts (question + multiple answers)
        qa_interventions = parse_qa_block(qa_block.strip(), call_start_utc, sequence)
        interventions.extend(qa_interventions)
        sequence += len(qa_interventions)
    
    # Sort by sequence to maintain order
    interventions.sort(key=lambda x: x['sequence_order'])
    
    return {
        'interventions': interventions,
        'full_transcript': content,
        'total_interventions': len(interventions),
        'total_speakers': len(set(i['speaker_name'] for i in interventions))
    }


def parse_intervention_block(block: str, call_start_utc: datetime, sequence: int, is_qa: bool) -> Dict:
    """Parse a single intervention block."""
    lines = block.split('\n')
    
    speaker_name = None
    speaker_role = None
    timestamp_str = None
    text_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith('SPEAKER:'):
            speaker_name = line.replace('SPEAKER:', '').strip()
        elif line.startswith('ROLE:'):
            speaker_role = line.replace('ROLE:', '').strip() or None
        elif line.startswith('TIME:'):
            timestamp_str = line.replace('TIME:', '').strip()
        elif line.startswith('TEXT:'):
            # Rest is text
            text_lines = [l for l in lines[i+1:] if l.strip()]
            break
        
        i += 1
    
    if not speaker_name or not timestamp_str:
        return None
    
    # Parse timestamp
    parts = timestamp_str.split(':')
    relative_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    timestamp_utc = call_start_utc + timedelta(seconds=relative_seconds)
    
    # Determine speaker type
    if speaker_name.lower() == 'operator':
        speaker_type = 'operator'
    elif is_qa:
        speaker_type = 'analyst' if 'analyst' in str(speaker_role).lower() else 'management'
    else:
        speaker_type = 'management'
    
    return {
        'timestamp_utc': timestamp_utc,
        'relative_seconds': relative_seconds,
        'relative_time': timestamp_str,
        'speaker_name': speaker_name,
        'speaker_role': speaker_role,
        'speaker_type': speaker_type,
        'text': '\n'.join(text_lines),
        'text_chars': len('\n'.join(text_lines)),
        'sequence_order': sequence,
        'is_qa_section': is_qa
    }


def parse_qa_block(block: str, call_start_utc: datetime, start_sequence: int) -> List[Dict]:
    """Parse a Q&A block (question + answers)."""
    interventions = []
    
    # Split into question and answer parts
    parts = []
    current_part = {'type': None, 'lines': []}
    
    for line in block.split('\n'):
        line_stripped = line.strip()
        
        if line_stripped.startswith('ANALYST:'):
            if current_part['type']:
                parts.append(current_part)
            current_part = {'type': 'question', 'lines': [line]}
        elif line_stripped.startswith('QUESTION:'):
            current_part['lines'].append(line)
        elif line_stripped.startswith('RESPONDER:'):
            if current_part['type']:
                parts.append(current_part)
            current_part = {'type': 'answer', 'lines': [line]}
        elif line_stripped.startswith('ANSWER:'):
            current_part['lines'].append(line)
        else:
            current_part['lines'].append(line)
    
    if current_part['type']:
        parts.append(current_part)
    
    # Parse each part
    question_id = None
    seq = start_sequence
    
    for part in parts:
        block_text = '\n'.join(part['lines'])
        
        if part['type'] == 'question':
            intervention = parse_question(block_text, call_start_utc, seq)
            if intervention:
                question_id = seq
                interventions.append(intervention)
                seq += 1
        
        elif part['type'] == 'answer':
            intervention = parse_answer(block_text, call_start_utc, seq, question_id)
            if intervention:
                interventions.append(intervention)
                seq += 1
    
    return interventions


def parse_question(block: str, call_start_utc: datetime, sequence: int) -> Dict:
    """Parse analyst question."""
    lines = block.split('\n')
    
    analyst_name = None
    company = None
    timestamp_str = None
    question_lines = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        if line.startswith('ANALYST:'):
            analyst_name = line.replace('ANALYST:', '').strip()
        elif line.startswith('COMPANY:'):
            company = line.replace('COMPANY:', '').strip()
        elif line.startswith('TIME:'):
            timestamp_str = line.replace('TIME:', '').strip()
        elif line.startswith('QUESTION:'):
            question_lines = [l.strip() for l in lines[i+1:] if l.strip()]
            break
    
    if not analyst_name or not timestamp_str:
        return None
    
    parts = timestamp_str.split(':')
    relative_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    timestamp_utc = call_start_utc + timedelta(seconds=relative_seconds)
    
    return {
        'timestamp_utc': timestamp_utc,
        'relative_seconds': relative_seconds,
        'relative_time': timestamp_str,
        'speaker_name': analyst_name,
        'speaker_role': company,
        'speaker_type': 'analyst',
        'text': '\n'.join(question_lines),
        'text_chars': len('\n'.join(question_lines)),
        'sequence_order': sequence,
        'is_qa_section': True,
        'is_question': True,
        'question_id': None,
        'analyst_firm': company
    }


def parse_answer(block: str, call_start_utc: datetime, sequence: int, question_id: int) -> Dict:
    """Parse management answer."""
    lines = block.split('\n')
    
    responder_name = None
    role = None
    timestamp_str = None
    answer_lines = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        if line.startswith('RESPONDER:'):
            responder_name = line.replace('RESPONDER:', '').strip()
        elif line.startswith('ROLE:'):
            role = line.replace('ROLE:', '').strip()
        elif line.startswith('TIME:'):
            timestamp_str = line.replace('TIME:', '').strip()
        elif line.startswith('ANSWER:'):
            answer_lines = [l.strip() for l in lines[i+1:] if l.strip()]
            break
    
    if not responder_name or not timestamp_str:
        return None
    
    parts = timestamp_str.split(':')
    relative_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    timestamp_utc = call_start_utc + timedelta(seconds=relative_seconds)
    
    return {
        'timestamp_utc': timestamp_utc,
        'relative_seconds': relative_seconds,
        'relative_time': timestamp_str,
        'speaker_name': responder_name,
        'speaker_role': role,
        'speaker_type': 'management',
        'text': '\n'.join(answer_lines),
        'text_chars': len('\n'.join(answer_lines)),
        'sequence_order': sequence,
        'is_qa_section': True,
        'is_answer': True,
        'question_id': question_id
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m aifinreport.ingestion.earnings_parser <file>")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    # NVDA Q2 FY2026 call: Aug 27, 2025, 5:00 PM EDT = 21:00 UTC
    call_start = datetime(2025, 8, 27, 21, 0, 0)
    
    result = parse_transcript_file(file_path, call_start)
    
    print(f"\n✅ Parsed {result['total_interventions']} interventions")
    print(f"   Unique speakers: {result['total_speakers']}")
    
    if result['interventions']:
        print(f"\n📋 First 5 interventions:\n")
        for intervention in result['interventions'][:5]:
            print(f"{intervention['sequence_order']}. {intervention['speaker_name']} ({intervention['speaker_type']})")
            if intervention.get('speaker_role'):
                print(f"   Role: {intervention['speaker_role']}")
            print(f"   Time: {intervention['relative_time']}")
            print(f"   Q&A: {intervention.get('is_qa_section', False)}")
            print(f"   Text: {intervention['text'][:80]}...")
            print()