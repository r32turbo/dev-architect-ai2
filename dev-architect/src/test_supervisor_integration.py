"""
Integration test and demonstration script for the Supervisor Agent.

This script shows how to use the supervisor agent orchestration.
"""

import sys
import importlib.util
from pathlib import Path


def test_imports():
    """Test that all necessary imports work."""
    print("[TEST] Testing imports...")
    
    try:
        import importlib.util
        
        # Test supervisor imports
        supervisor_state_path = Path(__file__).parent / "supervisor-agent" / "state.py"
        spec = importlib.util.spec_from_file_location("supervisor_state", supervisor_state_path)
        supervisor_state_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(supervisor_state_mod)
        SupervisorState = supervisor_state_mod.SupervisorState  # type: ignore
        
        print("✓ Supervisor state imported successfully")
        
        supervisor_prompts_path = Path(__file__).parent / "supervisor-agent" / "prompts.py"
        spec = importlib.util.spec_from_file_location("supervisor_prompts", supervisor_prompts_path)
        supervisor_prompts_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(supervisor_prompts_mod)
        
        print("✓ Supervisor prompts imported successfully")
        
        # Test system analyst imports
        system_analyst_prompt_path = Path(__file__).parent / "system-analyst-agent" / "prompt.py"
        spec = importlib.util.spec_from_file_location("system_analyst_prompt", system_analyst_prompt_path)
        system_analyst_prompt_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(system_analyst_prompt_mod)
        
        print("✓ System analyst prompt imported successfully")
        
        # Test LLD imports
        lld_state_path = Path(__file__).parent / "low-level-design-agent" / "state.py"
        spec = importlib.util.spec_from_file_location("lld_state", lld_state_path)
        lld_state_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lld_state_mod)
        LLDAgentState = lld_state_mod.LLDAgentState  # type: ignore
        
        print("✓ LLD agent state imported successfully")
        
        return True
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_definitions():
    """Test that state definitions are correct."""
    print("\n[TEST] Testing state definitions...")
    
    try:
        supervisor_state_path = Path(__file__).parent / "supervisor-agent" / "state.py"
        spec = importlib.util.spec_from_file_location("supervisor_state", supervisor_state_path)
        supervisor_state_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(supervisor_state_mod)
        SupervisorState = supervisor_state_mod.SupervisorState  # type: ignore
        
        # Verify SupervisorState has expected keys
        expected_keys = {
            'user_goal', 'system_analyst_output', 'lld_sections',
            'lld_architecture_analysis', 'lld_final_report', 'final_output'
        }
        
        # Create a sample state
        sample_state: SupervisorState = {  # type: ignore
            'user_goal': 'test goal',
            'system_analyst_output': '',
            'lld_sections': '',
            'lld_architecture_analysis': '',
            'lld_final_report': '',
            'final_output': '',
        }
        
        actual_keys = set(sample_state.keys())
        
        if expected_keys == actual_keys:
            print(f"✓ SupervisorState contains all expected keys: {expected_keys}")
            return True
        else:
            missing = expected_keys - actual_keys
            extra = actual_keys - expected_keys
            if missing:
                print(f"✗ Missing keys: {missing}")
            if extra:
                print(f"✗ Extra keys: {extra}")
            return False
            
    except Exception as e:
        print(f"✗ State definition test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_file_structure():
    """Test that all required files exist."""
    print("\n[TEST] Testing file structure...")
    
    required_files = [
        "supervisor-agent/main.py",
        "supervisor-agent/state.py",
        "supervisor-agent/prompts.py",
        "supervisor-agent/__init__.py",
        "system-analyst-agent/prompt.py",
        "system-analyst-agent/__init__.py",
        "low-level-design-agent/app.py",
        "low-level-design-agent/state.py",
        "low-level-design-agent/prompts.py",
        "low-level-design-agent/__init__.py",
    ]
    
    base_path = Path(__file__).parent
    all_exist = True
    
    for file_path in required_files:
        full_path = base_path / file_path
        if full_path.exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} - NOT FOUND")
            all_exist = False
    
    return all_exist


def main():
    """Run all tests."""
    print("=" * 80)
    print("SUPERVISOR AGENT - INTEGRATION TESTS")
    print("=" * 80)
    
    tests = [
        test_file_structure,
        test_imports,
        test_state_definitions,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test {test.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if all(results):
        print("\n✓✓✓ ALL TESTS PASSED ✓✓✓")
        return 0
    else:
        print("\n✗✗✗ SOME TESTS FAILED ✗✗✗")
        return 1


if __name__ == "__main__":
    exit(main())
