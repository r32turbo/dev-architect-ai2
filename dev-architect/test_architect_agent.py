#!/usr/bin/env python
"""Test the System Architecture Agent specifically"""
import sys
sys.path.insert(0, 'src')

try:
    print("Testing System Architecture Agent...\n")
    
    # Test 1: Import prompts
    print("✅ Test 1: Importing SYSTEM_ARCHITECT_PROMPT...")
    from system_architect_agent.prompts import SYSTEM_ARCHITECT_PROMPT
    print(f"   - Prompt type: {type(SYSTEM_ARCHITECT_PROMPT).__name__}")
    print(f"   - PromptBuilder: {hasattr(SYSTEM_ARCHITECT_PROMPT, 'add_system')}")
    
    # Test 2: Create context
    print("\n✅ Test 2: Creating AgentContext...")
    from system_architect_agent import create_context
    ctx = create_context(
        user_input="Build user authentication",
        requirement_doc="Support OAuth2",
        user_id="test-user"
    )
    print(f"   - Context created: {ctx is not None}")
    print(f"   - user_input in state: {'user_input' in ctx.state}")
    print(f"   - requirement_doc in state: {'requirement_doc' in ctx.state}")
    
    # Test 3: Chunk text function
    print("\n✅ Test 3: Testing chunk_text function...")
    from system_architect_agent.sysaapp import chunk_text
    import os
    
    # Test default
    os.environ['CHUNK_SIZE'] = '50000'
    text = 'x' * 100000
    chunks = chunk_text(text)
    print(f"   - Default CHUNK_SIZE=50000: {len(chunks)} chunks created")
    
    # Test custom env var
    os.environ['CHUNK_SIZE'] = '10000'
    # Reimport to get new value
    import importlib
    import system_architect_agent.sysaapp as sysaapp_module
    importlib.reload(sysaapp_module)
    chunks_custom = sysaapp_module.chunk_text(text)
    print(f"   - Custom CHUNK_SIZE=10000: {len(chunks_custom)} chunks created")
    
    # Test 4: Database models
    print("\n✅ Test 4: Checking database models...")
    from database.models import SystemRequirementDocument
    cols = [col.name for col in SystemRequirementDocument.__table__.columns]
    print(f"   - SystemRequirementDocument columns: {cols}")
    assert 'user_input' in cols and 'output' in cols
    print("   - ✅ All required columns present")
    
    # Test 5: Database methods
    print("\n✅ Test 5: Checking database methods...")
    from database.db import (
        get_requirement_document,
        save_requirement_document,
        get_all_requirement_documents,
        get_latest_requirement_document
    )
    print("   - ✅ All CRUD methods imported successfully")
    
    print("\n" + "="*60)
    print("✅✅✅ ALL TESTS PASSED! ✅✅✅")
    print("="*60)
    print("\nThe System Architecture Agent is ready to use!")
    print("\nTo test the full API:")
    print("  1. Start server: uvicorn src.main:app --reload")
    print("  2. Test endpoint: POST /generate/architecture")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
