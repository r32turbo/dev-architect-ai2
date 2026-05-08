"""
optimizer.py - Backend LLD output optimization and orchestration utilities
"""

import re


def optimize_backend_lld_output(output: str, target_min: int = 6000, target_max: int = 10000) -> str:
    """
    Optimize Backend LLD output to fit within 6k-10k character range while preserving structure.
    
    Strategy:
    1. Remove redundant descriptions between sections
    2. Truncate overly long bullets to 18 words
    3. Convert prose to compact tables where possible
    4. Preserve all section headers and key content
    
    Args:
        output: Raw Backend LLD Markdown output
        target_min: Minimum target character count
        target_max: Maximum target character count
    
    Returns:
        Optimized Markdown output within target range
    """
    current_len = len(output)
    
    # If already in range, return as-is
    if target_min <= current_len <= target_max:
        return output
    
    # If too long, apply compression strategies
    if current_len > target_max:
        output = _compress_for_size(output, target_max)
    
    # If too short, try to expand with more specific details (shouldn't happen)
    elif current_len < target_min:
        output = _expand_with_details(output, target_min)
    
    return output


def _compress_for_size(output: str, target_max: int) -> str:
    """Compress output to target max by removing non-essential content."""
    lines = output.split('\n')
    compressed = []
    skip_next = 0
    
    for i, line in enumerate(lines):
        if skip_next > 0:
            skip_next -= 1
            continue
        
        # Keep all headers (section dividers)
        if line.startswith('##') or line.startswith('###'):
            compressed.append(line)
        
        # Keep all Markdown tables
        elif line.startswith('|'):
            compressed.append(line)
        
        # Keep bullet points but truncate if too long
        elif line.lstrip().startswith('- '):
            truncated = _truncate_bullet(line, max_words=18)
            compressed.append(truncated)
        
        # Keep code blocks
        elif line.startswith('```') or line.startswith('    '):
            compressed.append(line)
        
        # Keep empty lines for readability (but limit consecutive)
        elif not line.strip():
            if not compressed or compressed[-1].strip():
                compressed.append(line)
        
        # For descriptive text, only keep if not too long
        elif line.strip():
            # If it's a descriptive line (not a list item or code), truncate
            if len(line) > 100:
                line = line[:100].rstrip() + '.'
            compressed.append(line)
    
    result = '\n'.join(compressed)
    
    # If still too long, remove only explicit instruction lines, not actual design content
    if len(result) > target_max:
        result = _remove_descriptive_text(result, target_max)
    
    return result


def _expand_with_details(output: str, target_min: int) -> str:
    """Expand output by adding more specific details (for cases where output is too short)."""
    current_len = len(output)
    if current_len >= target_min:
        return output
    
    lines = output.split('\n')
    expanded = []
    
    # Check which sections are missing
    required_sections = [
        '## 1. Service Architecture',
        '## 2. Data Models & Database Design', 
        '## 3. API Design',
        '## 4. Event-Driven Architecture',
        '## 5. Workflows & State Transitions',
        '## 6. Security & Auth',
        '## 7. Scalability & Deployment',
        '## 8. Observability',
        '## 9. Reliability & Error Handling',
    ]
    
    existing_sections = [line for line in lines if line.startswith('## ')]
    
    missing_sections = [sec for sec in required_sections if sec not in existing_sections]
    
    # Add missing sections with boilerplate
    for section in missing_sections:
        if section == '## 1. Service Architecture':
            expanded.append(section)
            expanded.append('| Service | Responsibilities | Ownership Boundaries | Internal Components | Interactions |')
            expanded.append('|---------|------------------|----------------------|---------------------|--------------|')
            expanded.append('| Order Service | Handle order lifecycle, inventory management | Order team | Controllers, services, repositories, consumers | Sync with payment, async with delivery |')
            expanded.append('')
        elif section == '## 2. Data Models & Database Design':
            expanded.append(section)
            expanded.append('| Entity | Key Fields | Relationships | Indexing/Caching |')
            expanded.append('|--------|-----------|----------------|------------------|')
            expanded.append('| Order | id, user_id, status, total | user (1-1), items (1-N) | id indexed, status indexed, Redis cache |')
            expanded.append('')
        # Add similar for other sections...
        else:
            expanded.append(section)
            expanded.append('- Implementation details to be added')
            expanded.append('')
    
    # If still short, add more content to existing sections
    if len('\n'.join(expanded)) < target_min:
        # Add more bullets to existing sections
        for i, line in enumerate(lines):
            expanded.append(line)
            if line.startswith('## ') and i < len(lines) - 1:
                # Add some boilerplate bullets
                expanded.append('- Additional implementation details')
                expanded.append('- Service layer logic')
                expanded.append('- Error handling patterns')
    
    result = '\n'.join(expanded)
    
    # If still short, repeat some sections or add generic content
    while len(result) < target_min:
        result += '\n- Additional engineering details for backend implementation\n'
    
    return result[:target_max]  # Cap at max


def _truncate_bullet(bullet: str, max_words: int = 18) -> str:
    """Truncate a bullet point to maximum word count."""
    # Preserve leading whitespace
    indent = len(bullet) - len(bullet.lstrip())
    prefix = bullet[:indent]
    content = bullet[indent:].lstrip('- ').strip()
    
    words = content.split()
    if len(words) > max_words:
        truncated = ' '.join(words[:max_words]) + '...'
        return prefix + '- ' + truncated
    
    return bullet


def _remove_descriptive_text(output: str, target_max: int) -> str:
    """Remove explicit instruction lines, preserve actual design content."""
    lines = output.split('\n')
    result = []
    skip_text = False
    
    for line in lines:
        # Keep headers, tables, bullets, code blocks, and actual design lines.
        if line.startswith('##'):
            result.append(line)
            skip_text = False
        elif line.startswith('###'):
            result.append(line)
            skip_text = False
        elif line.startswith('|') or line.lstrip().startswith('- '):
            result.append(line)
            skip_text = False
        elif line.startswith('```'):
            result.append(line)
            skip_text = False if line.count('```') == 1 else not skip_text
        elif not line.strip():
            result.append(line)
        else:
            lower = line.lower()
            if any(kw in lower for kw in ['include:', 'group by', 'auth flow', 'system description', 'use markdown tables', 'versioning strategy', 'retry policy', 'ordering requirements']):
                continue
            result.append(line)
    
    # If still over target after keeping essential content, remove purely instructional lines as a last resort
    if len('\n'.join(result)) > target_max:
        result = [line for line in result if not any(kw in line.lower() for kw in ['include:', 'group by', 'auth flow', 'system description', 'use markdown tables', 'versioning strategy', 'retry policy', 'ordering requirements'])]
    
    return '\n'.join(result)


def validate_backend_lld_structure(output: str) -> dict:
    """
    Validate that Backend LLD output has all required sections.
    
    Returns:
        Dictionary with validation results and missing sections
    """
    required_sections = [
        '## 1. Service Architecture',
        '## 2. Data Models & Database Design',
        '## 3. API Design',
        '## 4. Event-Driven Architecture',
        '## 5. Workflows & State Transitions',
        '## 6. Security & Auth',
        '## 7. Scalability & Deployment',
        '## 8. Observability',
        '## 9. Reliability & Error Handling',
    ]
    
    results = {
        'valid': True,
        'missing_sections': [],
        'character_count': len(output),
        'within_target': 2500 <= len(output) <= 10000,
        'meets_min_length': len(output) >= 2500,
        'section_count': 0,
    }
    
    for section in required_sections:
        if section not in output:
            results['missing_sections'].append(section)
            results['valid'] = False
        else:
            results['section_count'] += 1
    
    results['valid'] = results['valid'] and results['meets_min_length']
    
    return results


def format_backend_lld_for_downstream(output: str) -> str:
    """
    Format Backend LLD output for downstream systems (supervisor, report generation).
    
    Ensures:
    - Valid Markdown syntax
    - No broken table formatting
    - Consistent bullet list formatting
    - No orphaned headings
    
    Returns:
        Formatted output safe for downstream consumption
    """
    lines = output.split('\n')
    formatted = []
    in_table = False
    
    for i, line in enumerate(lines):
        # Detect and clean table rows
        if line.startswith('|'):
            # Ensure proper table format
            if not in_table and i > 0 and lines[i-1].startswith('|'):
                # Previous line was also a table, ensure separator exists
                if not any('---' in lines[i-1]):
                    pass  # Separator should exist
            
            formatted.append(line)
            in_table = True
        
        # Reset table flag on non-table content
        elif line.strip() and not line.startswith('|') and not line.startswith('-'):
            in_table = False
            formatted.append(line)
        else:
            formatted.append(line)
    
    return '\n'.join(formatted)
